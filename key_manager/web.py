"""FastAPI application for API Key Manager.

Serves the web UI and REST API for managing API keys across 37+ providers.
"""

import time
import asyncio
import os
import json
import hmac
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
import pydantic
from fastapi import FastAPI, Request, Query, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from fastapi.templating import Jinja2Templates

from key_manager.config import load_config
from key_manager.parser import import_keys, mask_key, validate_import_path
from key_manager.validator import validate_keys
from key_manager.checker import run_check
from key_manager.tester import run_test
from key_manager.proxy import get_proxy, detect_system_proxy
from key_manager.storage import KeyStore
from key_manager.providers import (
    PROVIDERS,
    get_display_name,
    DISPLAY_NAMES,
    PROVIDER_WEBSITES,
    KEY_PREFIX_MAP,
)
from key_manager.providers.models_registry import PROVIDER_MODELS
from key_manager.providers.base import simplify_error, CheckResult
from key_manager.detector import detect_by_prefix, detect_provider
from key_manager.logger import project_logger
from key_manager.i18n import get_lang_from_header, set_lang, t
from key_manager.webhook import webhook_manager, WebhookEvent
from key_manager.ssrf import validate_custom_base_url, get_allowed_domains
from key_manager.url_override import custom_base_url
from key_manager.errors import (
    ErrorCode,
    ErrorResponse,
    KeyManagerError,
    ValidationError,
    StorageError,
    ProviderError,
    SystemError,
)

from key_manager.api_models import (
    KeyInfo,
    KeyListResponse,
    KeyExportItem,
    KeyExportResponse,
    ImportRequest,
    ImportResponse,
    CheckSingleRequest,
    CheckSingleResponse,
    CheckBatchItem,
    CheckBatchRequest,
    CheckBatchResult,
    CheckBatchSummary,
    CheckBatchResponse,
    TestSingleRequest,
    TestSingleResponse,
    BalanceRequest,
    BalanceResponse,
    ModelInfo,
    ModelsResponse,
    ProviderInfo as ProviderInfoModel,
    ProvidersResponse,
    ProviderDetail,
    ProviderDetailResponse,
    StatsProviderEntry,
    StatsResponse,
    StatsChartProviderEntry,
    StatsChartStatuses,
    StatsChartResponse,
    LogEntry,
    LogsResponse,
    OperationEntry,
    OperationsResponse,
    ProgressResponse,
    ProxyResponse,
)

# Module-level config

config = load_config()

# Debug system
try:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from webdebug import init_debug, debug_logger, FunctionTracer
    DEBUG_ENABLED = True
except ImportError:
    DEBUG_ENABLED = False
    debug_logger = None
    FunctionTracer = None
# FastAPI application

app = FastAPI(
    title="API Key Manager",
    description="Manage and validate API keys for 37+ AI providers. "
    "Import, check validity, test token limits and concurrency, "
    "query balances, and export working keys.",
    version="3.0.1",
    openapi_tags=[
        {"name": "Keys", "description": "Key management operations"},
        {"name": "Check", "description": "Key validity checking"},
        {"name": "Test", "description": "Token limit & concurrency testing"},
        {"name": "Balance", "description": "Account balance queries"},
        {"name": "Models", "description": "Available model queries"},
        {"name": "Providers", "description": "Provider registry & details"},
        {"name": "Stats", "description": "Statistics & charts"},
        {"name": "Logs", "description": "Operation logs"},
        {"name": "Progress", "description": "Long-running task progress"},
    ],
)

# CORS middleware
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # Must be False when allow_origins is "*" (CORS spec)
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize debug system

if DEBUG_ENABLED:
    debug_tracer = init_debug(app)
    tracer = FunctionTracer(debug_logger, category="API")
else:
    debug_tracer = None
    tracer = None

# Global progress tracker (shared-memory, thread-safe)

class ProgressTracker:
    """Thread-safe progress tracker for long-running operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active = False
        self._current = 0
        self._total = 0
        self._status = ""
        self._results: dict[str, Any] | None = None

    def start(self, total: int, status: str = "loading"):
        with self._lock:
            self._active = True
            self._current = 0
            self._total = total
            self._status = status
            self._results = None

    def update(self, current: int, total: int):
        with self._lock:
            self._current = current
            self._total = total

    def done(self, status: str = "done", results: dict[str, Any] | None = None):
        with self._lock:
            self._active = False
            self._current = self._total
            self._status = status
            self._results = results

    def snapshot(self) -> ProgressResponse:
        with self._lock:
            return ProgressResponse(
                active=self._active,
                current=self._current,
                total=self._total,
                status=self._status,
                results=self._results,
            )


_progress_tracker = ProgressTracker()


def _make_progress_callback():
    """Return a (current, total) callable that updates the global tracker."""
    def cb(current: int, total: int):
        _progress_tracker.update(current, total)
    return cb


# SSE helpers

async def _sse_progress_event_generator(poll_interval: float = 0.5):
    """SSE generator that polls the progress tracker until the task completes."""
    while True:
        snap = _progress_tracker.snapshot()
        data = snap.model_dump_json()
        yield f"data: {data}\n\n"
        if not snap.active:
            yield "data: [DONE]\n\n"
            break
        await asyncio.sleep(poll_interval)


# Helper: load keys store

def _load_keys_store(config_override: dict | None = None) -> KeyStore:
    cfg = config_override or config
    return KeyStore(cfg["storage"]["keys_file"], cfg)


def _load_keys_data(config_override: dict | None = None) -> dict:
    cfg = config_override or config
    try:
        return _load_keys_store(cfg).load()
    except Exception:
        keys_path = Path(cfg["storage"]["keys_file"])
        if not keys_path.exists():
            return {"keys": {}}
        with open(keys_path, "r", encoding="utf-8") as f:
            return json.load(f)


def _save_keys_data(data: dict, config_override: dict | None = None):
    cfg = config_override or config
    _load_keys_store(cfg).save(data)


# Middleware: rate limit by IP

_RATE_LIMIT_STORE: dict[str, list[float]] = {}


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Skip for static/docs and auth whitelist
    if request.url.path in _AUTH_WHITELIST or request.url.path.startswith("/static"):
        return await call_next(request)

    rate_limit_config = config.get("rate_limit", {})
    requests_per_minute = rate_limit_config.get("requests_per_minute", 60)
    if not requests_per_minute:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old entries
    if client_ip in _RATE_LIMIT_STORE:
        _RATE_LIMIT_STORE[client_ip] = [t for t in _RATE_LIMIT_STORE[client_ip] if now - t < 60.0]
    else:
        _RATE_LIMIT_STORE[client_ip] = []

    if len(_RATE_LIMIT_STORE[client_ip]) >= requests_per_minute:
        return JSONResponse(
            status_code=429,
            content={"error": {"code": "RATE_LIMITED", "message": "Too many requests", "details": {"retry_after": 1}}}
        )

    _RATE_LIMIT_STORE[client_ip].append(now)
    return await call_next(request)

# Middleware: authenticate requests via Bearer token

_AUTH_WHITELIST = {"/", "/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    api_key = config.get("auth", {}).get("api_key", "") or os.environ.get("KEY_MANAGER_API_KEY", "")
    if not api_key:
        # Log warning once at startup (not on every request)
        if not hasattr(app, '_auth_warning_logged'):
            import logging
            logging.getLogger(__name__).warning(
                "Authentication is disabled. Set KEY_MANAGER_API_KEY env var or "
                "auth.api_key in config.yaml to secure your API."
            )
            app._auth_warning_logged = True
        return await call_next(request)
    if request.url.path in _AUTH_WHITELIST:
        return await call_next(request)
    auth_header = request.headers.get("authorization", "")
    if hmac.compare_digest(auth_header, f"Bearer {api_key}"):
        return await call_next(request)
    response = ErrorResponse.error_factory(
        code=ErrorCode.AUTH_REQUIRED,
        message=t(ErrorCode.AUTH_REQUIRED.value),
    )
    return JSONResponse(status_code=401, content=response.model_dump())

# Middleware: set language from Accept-Language header

@app.middleware("http")
async def i18n_middleware(request: Request, call_next):
    lang = get_lang_from_header(request.headers.get("accept-language"))
    set_lang(lang)
    response = await call_next(request)
    return response


# Error handlers


@app.exception_handler(RequestValidationError)
async def pydantic_validation_error_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic/body validation errors to 400 with structured ErrorResponse."""
    errors = []
    code = ErrorCode.VALIDATION_MISSING_KEY
    for err in exc.errors():
        loc_list = err.get("loc", [])
        msg = err.get("msg", "")
        loc_str = ".".join(str(x) for x in loc_list)
        errors.append(f"{loc_str}: {msg}")
        if "key" in loc_list:
            code = ErrorCode.VALIDATION_MISSING_KEY
        elif "file" in loc_list:
            code = ErrorCode.VALIDATION_FILE_NOT_FOUND
        elif "provider" in loc_list:
            code = ErrorCode.VALIDATION_PROVIDER_UNKNOWN

    response = ErrorResponse.error_factory(
        code=code,
        message=t(code.value),
        details={"validation_errors": errors},
    )
    return JSONResponse(status_code=400, content=response.model_dump())


@app.exception_handler(KeyManagerError)
async def key_manager_error_handler(request: Request, exc: KeyManagerError):
    status_code, body = exc.to_response()
    return JSONResponse(status_code=status_code, content=body.model_dump())


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    status_code, body = exc.to_response()
    return JSONResponse(status_code=status_code, content=body.model_dump())


# ---
# WEB UI
# ---

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
_TEMPLATES_DIR_ALT = Path(__file__).resolve().parent / "templates"

if _TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
elif _TEMPLATES_DIR_ALT.exists():
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR_ALT))
else:
    templates = None


@app.get("/", include_in_schema=False)
async def web_ui(request: Request):
    """Serve the web UI."""
    if templates and (_TEMPLATES_DIR / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request})
    if templates and (_TEMPLATES_DIR_ALT / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<html><body><h1>API Key Manager</h1><p>Web UI not found.</p></body></html>")


# ---
# KEYS
# ---

@app.post("/api/import", tags=["Keys"], response_model=ImportResponse)
async def api_import(body: ImportRequest):
    """Import keys from a JSON file, directory, or inline batch."""
    data = _load_keys_data()

    if body.batch:
        # Inline batch import
        timestamp = datetime.utcnow().isoformat() + "Z"
        new = 0
        dupes = 0
        errors: list[str] = []
        for raw_key in body.batch:
            if not raw_key or not isinstance(raw_key, str):
                errors.append(f"Invalid key: {raw_key}")
                continue
            key = raw_key.strip()
            if not key:
                errors.append("Empty key in batch")
                continue
            if key in data.get("keys", {}):
                dupes += 1
                continue
            data.setdefault("keys", {})[key] = {
                "key_masked": mask_key(key),
                "provider": "unknown",
                "provider_detected": None,
                "status": "unknown",
                "sources": [{"file": "batch", "batch": "manual", "imported_at": timestamp}],
                "checks": [],
                "tests": {},
                "first_seen": timestamp,
                "last_checked": None,
                "last_tested": None,
                "created_at": timestamp,
            }
            new += 1
        _save_keys_data(data)
        project_logger.log_web_action("import", f"batch: {new} new, {dupes} dupes")
        return ImportResponse(new=new, duplicates=dupes, errors=errors)

    allowed_dirs = config.get("scan", {}).get("directories", ["./data/input"])
    if body.file:
        validate_import_path(body.file, allowed_dirs)
    if body.directory:
        validate_import_path(body.directory, allowed_dirs)

    if not body.file and not body.directory:
        body.directory = config["scan"]["directories"][0]

    new, dupes, errors = import_keys(
        file_path=body.file,
        directory=body.directory,
        batch=None,
        keys_file=config["storage"]["keys_file"],
    )
    project_logger.log_web_action("import", f"{body.file or body.directory}: {new} new, {dupes} dupes")
    return ImportResponse(new=new, duplicates=dupes, errors=errors)


@app.post("/api/import/upload", tags=["Keys"])
async def api_import_upload(request: Request):
    """Upload and import a JSON key file."""
    file = None
    filename = ""
    try:
        form = await request.form()
        file = form.get("file")
        if hasattr(file, "filename"):
            filename = file.filename or ""
    except Exception:
        pass

    if not file or not filename:
        response = ErrorResponse.error_factory(
            code=ErrorCode.VALIDATION_FILE_NOT_FOUND,
            message=t("VALIDATION_FILE_NOT_FOUND"),
        )
        return JSONResponse(status_code=400, content=response.model_dump())

    if not filename.endswith(".json"):
        raise ValidationError(
            code=ErrorCode.VALIDATION_FILE_FORMAT,
            message=t("VALIDATION_FILE_FORMAT"),
        )

    content = await file.read()
    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        raise ValidationError(
            code=ErrorCode.VALIDATION_FILE_FORMAT,
            message="Uploaded file is not valid JSON",
        )

    if not isinstance(items, list):
        raise ValidationError(
            code=ErrorCode.VALIDATION_FILE_FORMAT,
            message="Uploaded JSON must be an array of key objects",
        )

    keys_file = config["storage"]["keys_file"]
    logs_dir = config["storage"].get("logs_dir", "./data/logs")
    allowed_dirs = [logs_dir, "./data/input"]
    tmp_path = validate_import_path(str(Path(logs_dir).parent / "input" / filename), allowed_dirs)
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(content)

    new, dupes, errors = import_keys(
        file_path=str(tmp_path),
        keys_file=keys_file,
    )

    # Clean up temp file
    try:
        tmp_path.unlink()
    except Exception:
        pass

    project_logger.log_web_action("import_upload", f"{filename}: {new} new, {dupes} dupes")
    return ImportResponse(new=new, duplicates=dupes, errors=errors)


@app.get("/api/keys", tags=["Keys"], response_model=KeyListResponse)
async def api_list_keys(
    provider: str = Query(None, description="Filter by provider"),
    status: str = Query(None, description="Filter by status"),
    batch: str = Query(None, description="Filter by batch label"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
):
    """List keys with optional filters and pagination."""
    data = _load_keys_data()
    keys_dict = data.get("keys", {})

    filtered: list[tuple[str, dict]] = []
    for key, info in keys_dict.items():
        if provider and info.get("provider", "").lower() != provider.lower():
            continue
        if status and info.get("status") != status:
            continue
        if batch:
            has_batch = any(s.get("batch") == batch for s in info.get("sources", []))
            if not has_batch:
                continue
        filtered.append((key, info))

    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    paged = filtered[start:end]

    key_infos: list[KeyInfo] = []
    for key, info in paged:
        key_infos.append(KeyInfo(
            key_masked=info.get("key_masked", mask_key(key)),
            provider=info.get("provider", "unknown"),
            status=info.get("status", "unknown"),
            last_checked=info.get("last_checked"),
            last_error=info.get("last_error"),
            error_type=info.get("error_type"),
            tests=info.get("tests", {}),
            models=info.get("tests", {}).get("models", []),
            sources_count=len(info.get("sources", [])),
            balance=info.get("balance"),
        ))

    return KeyListResponse(
        keys=key_infos,
        total=total,
        page=page,
        total_pages=total_pages,
        page_size=page_size,
    )


@app.get("/api/keys/export", tags=["Keys"], response_model=KeyExportResponse)
async def api_export_keys(
    provider: str = Query(None, description="Filter by provider"),
):
    """Export all valid keys."""
    data = _load_keys_data()
    keys_dict = data.get("keys", {})

    exported: list[KeyExportItem] = []
    for key, info in keys_dict.items():
        if info.get("status") != "valid":
            continue
        if provider and info.get("provider", "").lower() != provider.lower():
            continue
        tests = info.get("tests", {})
        exported.append(KeyExportItem(
            key_masked=info.get("key_masked", mask_key(key)),
            provider=info.get("provider", "unknown"),
            max_tokens=tests.get("max_tokens"),
            max_concurrency=tests.get("max_concurrency"),
        ))

    project_logger.log_web_action("export", f"{len(exported)} keys")
    return KeyExportResponse(keys=exported, total=len(exported))


@app.post("/api/keys/clear", tags=["Keys"])
async def api_clear_keys():
    """Clear all keys from storage."""
    cfg = config
    keys_path = Path(cfg["storage"]["keys_file"])
    cleared = 0
    if keys_path.exists():
        data = _load_keys_data()
        cleared = len(data.get("keys", {}))
        data["keys"] = {}
        _save_keys_data(data)
    project_logger.log_web_action("clear", f"{cleared} keys removed")
    return {"cleared": cleared}


# ---
# CHECK
# ---

@app.post("/api/check", tags=["Check"])
async def api_check(
    provider: str = Form(None),
    status: str = Form(None),
    body_json: dict = Body(None),
):
    """Run a validation check against all keys (synchronous - returns results directly)."""
    # Support both form data and JSON body
    p = provider or (body_json or {}).get("provider")
    s = status or (body_json or {}).get("status")

    proxy = get_proxy(config.get("proxy")) or None
    results = await validate_keys(
        keys_file=config["storage"]["keys_file"],
        results_file=config["storage"]["check_results_file"],
        logs_dir=config["storage"]["logs_dir"],
        concurrency=config["check"]["concurrency"],
        timeout=config["check"]["timeout_seconds"],
        proxy=proxy,
        provider_filter=p or None,
        status_filter=s or None,
        progress_callback=_make_progress_callback(),
    )
    project_logger.log_web_action("check_all", f"total={results.get('total', 0)}")

    # Dispatch webhook
    asyncio.create_task(
        webhook_manager.dispatch(
            WebhookEvent.BATCH_CHECK_COMPLETED,
            {"total": results.get("total", 0)},
        )
    )

    return results


@app.post("/api/check/single", tags=["Check"], response_model=CheckSingleResponse)
async def api_check_single(body: CheckSingleRequest):
    """Check validity of a single API key."""
    key = (body.key or "").strip()
    provider_name = (body.provider or "").strip()

    custom_url = body.custom_base_url
    if custom_url:
        allowed_domains = get_allowed_domains(PROVIDERS)
        validate_custom_base_url(custom_url, allowed_domains)
        custom_base_url.set(custom_url)
    if not key:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    # Detect provider if not given - use smart detection with probe+check verification
    proxy = get_proxy(config.get("proxy")) or None
    
    # Debug logging for proxy config
    if DEBUG_ENABLED and debug_logger:
        import asyncio as _asyncio
        _asyncio.create_task(debug_logger.log(
            category="DETECT",
            action="config",
            detail=f"proxy={proxy}, timeout={config['check']['timeout_seconds']}s",
            data={"proxy": proxy, "timeout": config['check']['timeout_seconds']},
            level="INFO"
        ))
    
    try:
        async with httpx.AsyncClient(
            timeout=config["check"]["timeout_seconds"],
            proxy=proxy,
            follow_redirects=False,
        ) as client:
            if not provider_name:
                provider_name = await detect_provider(client, key)
                if not provider_name or provider_name == 'unknown':
                    raise ValidationError(
                        code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                        message=t("VALIDATION_PROVIDER_UNKNOWN"),
                    )

            provider_name_lower = provider_name.lower()
            provider_obj = PROVIDERS.get(provider_name_lower)
            if not provider_obj:
                raise ValidationError(
                    code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                    message=t("VALIDATION_PROVIDER_UNKNOWN"),
                )

            # If provider was auto-detected, the detection already validated the key
            # Only call check() if provider was manually specified
            model_name = body.model
            from key_manager.providers.base import CheckResult
            if body.provider:
                if model_name:
                    # Test specific model only
                    import time as _time
                    import re as _re
                    headers = provider_obj.build_headers(key)
                    headers["Content-Type"] = "application/json"
                    # Extract version path from check_endpoint
                    version_match = _re.match(r'(/v\d+)', provider_obj.check_endpoint or '')
                    version_prefix = version_match.group(1) if version_match else ''
                    chat_url = f"{provider_obj.get_base_url()}{version_prefix}/chat/completions"
                    start = _time.monotonic()
                    try:
                        resp = await client.post(
                            chat_url,
                            headers=headers,
                            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                        )
                        latency = (_time.monotonic() - start) * 1000
                        if resp.status_code == 200:
                            result = CheckResult(valid=True, status_code=200, latency_ms=latency, error=None)
                        else:
                            error_msg = f"status {resp.status_code}"
                            try:
                                error_msg = resp.json().get("error", {}).get("message", error_msg)
                            except:
                                pass
                            result = CheckResult(valid=False, status_code=resp.status_code, latency_ms=latency, error=error_msg)
                    except Exception as e:
                        result = CheckResult(valid=False, status_code=None, latency_ms=(_time.monotonic() - start) * 1000, error=str(e))
                else:
                    result = await provider_obj.check(client, key)
            else:
                # Provider was auto-detected, still need to validate the key
                if model_name:
                    # Test specific model only
                    import time as _time
                    import re as _re
                    headers = provider_obj.build_headers(key)
                    headers["Content-Type"] = "application/json"
                    # Extract version path from check_endpoint
                    version_match = _re.match(r'(/v\d+)', provider_obj.check_endpoint or '')
                    version_prefix = version_match.group(1) if version_match else ''
                    chat_url = f"{provider_obj.get_base_url()}{version_prefix}/chat/completions"
                    start = _time.monotonic()
                    try:
                        resp = await client.post(
                            chat_url,
                            headers=headers,
                            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5}
                        )
                        latency = (_time.monotonic() - start) * 1000
                        if resp.status_code == 200:
                            result = CheckResult(valid=True, status_code=200, latency_ms=latency, error=None)
                        else:
                            error_msg = f"status {resp.status_code}"
                            try:
                                error_msg = resp.json().get("error", {}).get("message", error_msg)
                            except:
                                pass
                            result = CheckResult(valid=False, status_code=resp.status_code, latency_ms=latency, error=error_msg)
                    except Exception as e:
                        result = CheckResult(valid=False, status_code=None, latency_ms=(_time.monotonic() - start) * 1000, error=str(e))
                else:
                    result = await provider_obj.check(client, key)
            # Attempt balance query
            balance = None
            if result.valid and hasattr(provider_obj, "get_balance"):
                try:
                    bal = await provider_obj.get_balance(client, key)
                    if bal.supported and bal.balance is not None:
                        balance = {"balance": bal.balance, "currency": bal.currency}
                except Exception:
                    pass

            # Attempt models query
            models: list[str] = []
            if result.valid and hasattr(provider_obj, "get_models"):
                try:
                    models = await provider_obj.get_models(client, key) or []
                except Exception:
                    pass

            error_type = None
            if not result.valid:
                if result.status_code in (401, 403):
                    error_type = "invalid_key"
                elif result.status_code == 429:
                    error_type = "rate_limited"
                elif result.status_code == 402:
                    error_type = "insufficient_balance"

            status_str = "valid" if result.valid else ("invalid" if result.status_code in (401, 403) else "error")

            project_logger.log_web_action("check_single", f"{mask_key(key)} {provider_name}: {status_str}")

            # Simplify error message for readability
            simplified_error = simplify_error(result.error, result.status_code) if result.error else None

            return CheckSingleResponse(
                key=key,
                key_masked=mask_key(key),
                provider=provider_name,
                display_name=get_display_name(provider_name),
                status=status_str,
                status_code=result.status_code,
                latency_ms=result.latency_ms,
                error=simplified_error,
                error_type=error_type,
                balance=balance,
                models=models,
            )
    finally:
        custom_base_url.set(None)


@app.post("/api/check/batch", tags=["Check"], response_model=CheckBatchResponse)
async def api_check_batch(body: CheckBatchRequest):
    """Check validity of multiple keys in batch."""
    if not body.keys:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    proxy = get_proxy(config.get("proxy")) or None
    results: list[CheckBatchResult] = []
    summary = CheckBatchSummary()

    sem = asyncio.Semaphore(body.concurrency or 50)

    async def _check_one(item: CheckBatchItem):
        key = (item.key or "").strip()
        provider_name = (item.provider or "").strip()

        if not key:
            return CheckBatchResult(
                key_masked="(empty)",
                provider="unknown",
                status="error",
                error="Empty key provided",
            )

        if not provider_name:
            # Use detect_provider for robust detection
            try:
                async with httpx.AsyncClient(timeout=10, proxy=proxy) as detect_client:
                    provider_name = await detect_provider(detect_client, key)
            except Exception:
                pass
            if not provider_name or provider_name == 'unknown':
                candidates = detect_by_prefix(key)
                provider_name = candidates[0] if candidates else "unknown"
        else:
            provider_name = provider_name.lower()

        provider_obj = PROVIDERS.get(provider_name)
        if not provider_obj:
            return CheckBatchResult(
                key_masked=mask_key(key),
                provider=provider_name,
                status="error",
                error=f"Unknown provider: {provider_name}",
            )

        async with sem:
            async with httpx.AsyncClient(
                timeout=body.timeout or 10,
                proxy=proxy,
                follow_redirects=False,
            ) as client:
                result = await provider_obj.check(client, key)

        status_str = "valid" if result.valid else ("invalid" if result.status_code in (401, 403) else "error")
        return CheckBatchResult(
            key_masked=mask_key(key),
            provider=provider_name,
            status=status_str,
            status_code=result.status_code,
            latency_ms=result.latency_ms,
            error=result.error,
            error_type=getattr(result, "error_type", None),
        )

    tasks = [_check_one(item) for item in body.keys]
    batch_results = await asyncio.gather(*tasks)

    for r in batch_results:
        results.append(r)
        if r.status == "valid":
            summary.valid += 1
        elif r.status == "invalid":
            summary.invalid += 1
        else:
            summary.error += 1

    summary.total = len(batch_results)
    project_logger.log_web_action("check_batch", f"total={summary.total}, valid={summary.valid}")

    return CheckBatchResponse(results=results, summary=summary)


# ---
# TEST
# ---

@app.post("/api/test", tags=["Test"])
async def api_test():
    """Run token limit and concurrency tests against all valid keys (async)."""
    proxy = get_proxy(config.get("proxy")) or None

    async def _run():
        try:
            results = await run_test(
                keys_file=config["storage"]["keys_file"],
                results_file=config["storage"]["test_results_file"],
                logs_dir=config["storage"]["logs_dir"],
                timeout=config["test"]["concurrency_timeout_seconds"],
                proxy=proxy,
                token_test=config["test"].get("token_test", True),
                concurrency_test=config["test"].get("concurrency_test", True),
                token_steps=config["test"]["token_steps"],
                concurrency_steps=config["test"]["concurrency_steps"],
                progress_callback=_make_progress_callback(),
            )
            _progress_tracker.done("done", results)
            project_logger.log_web_action("test_all", f"tested={results.get('total_tested', 0)}")
            await webhook_manager.dispatch(
                WebhookEvent.BATCH_TEST_COMPLETED,
                {"total_tested": results.get("total_tested", 0)},
            )
        except Exception as e:
            _progress_tracker.done("error", {"error": str(e)})
            await webhook_manager.dispatch(
                WebhookEvent.ERROR_OCCURRED,
                {"error": str(e)},
            )

    _progress_tracker.start(total=0, status="loading")
    asyncio.create_task(_run())
    return {"message": "Test started", "status": "loading"}


@app.post("/api/test/single", tags=["Test"], response_model=TestSingleResponse)
async def api_test_single(body: TestSingleRequest):
    """Test token limit and concurrency for a single key."""
    key = (body.key or "").strip()
    provider_name = (body.provider or "").strip()

    if not key:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    if not provider_name:
        proxy = get_proxy(config.get("proxy")) or None
        async with httpx.AsyncClient(timeout=config["check"]["timeout_seconds"], proxy=proxy) as client:
            provider_name = await detect_provider(client, key)
        if not provider_name or provider_name == 'unknown':
            raise ValidationError(
                code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                message=t("VALIDATION_PROVIDER_UNKNOWN"),
            )

    provider_name_lower = provider_name.lower()
    provider_obj = PROVIDERS.get(provider_name_lower)
    if not provider_obj:
        raise ValidationError(
            code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
            message=t("VALIDATION_PROVIDER_UNKNOWN"),
        )

    proxy = get_proxy(config.get("proxy")) or None
    token_steps = config["test"]["token_steps"]
    concurrency_steps = config["test"]["concurrency_steps"]

    max_tokens = None
    max_concurrency = None
    models: list[str] = []
    error = None

    async with httpx.AsyncClient(
        timeout=config["test"]["concurrency_timeout_seconds"],
        proxy=proxy,
    ) as client:
        # Token test
        try:
            token_result = await provider_obj.test_token_limit(client, key, token_steps)
            max_tokens = token_result.max_tokens
            if token_result.error:
                error = token_result.error
        except Exception as e:
            if not error:
                error = str(e)

        # Concurrency test
        try:
            conc_result = await provider_obj.test_concurrency(client, key, concurrency_steps)
            max_concurrency = conc_result.max_concurrency
            if conc_result.error and not error:
                error = conc_result.error
        except Exception as e:
            if not error:
                error = str(e)

        # Models
        try:
            if hasattr(provider_obj, "get_models"):
                models = await provider_obj.get_models(client, key) or []
        except Exception:
            pass

    project_logger.log_web_action(
        "test_single",
        f"{mask_key(key)} {provider_name}: tokens={max_tokens}, concurrency={max_concurrency}",
    )

    return TestSingleResponse(
        provider=provider_name,
        key_masked=mask_key(key),
        max_tokens=max_tokens,
        max_concurrency=max_concurrency,
        models=models,
        error=error,
    )


@app.post("/api/test/token", tags=["Test"])
async def api_test_token():
    """Run token limit tests on all valid keys (async)."""
    proxy = get_proxy(config.get("proxy")) or None

    async def _run():
        try:
            results = await run_test(
                keys_file=config["storage"]["keys_file"],
                results_file=config["storage"]["test_results_file"],
                logs_dir=config["storage"]["logs_dir"],
                timeout=config["test"]["concurrency_timeout_seconds"],
                proxy=proxy,
                token_test=True,
                concurrency_test=False,
                token_steps=config["test"]["token_steps"],
                progress_callback=_make_progress_callback(),
            )
            _progress_tracker.done("done", results)
        except Exception as e:
            _progress_tracker.done("error", {"error": str(e)})

    _progress_tracker.start(total=0, status="loading")
    asyncio.create_task(_run())
    return {"message": "Token test started", "status": "loading"}


@app.post("/api/test/token/batch", tags=["Test"], include_in_schema=False)
async def api_test_token_batch():
    """Run token limit tests on specific keys (batch alias)."""
    return await api_test_token()


@app.post("/api/test/concurrency", tags=["Test"])
async def api_test_concurrency():
    """Run concurrency tests on all valid keys (async)."""
    proxy = get_proxy(config.get("proxy")) or None

    async def _run():
        try:
            results = await run_test(
                keys_file=config["storage"]["keys_file"],
                results_file=config["storage"]["test_results_file"],
                logs_dir=config["storage"]["logs_dir"],
                timeout=config["test"]["concurrency_timeout_seconds"],
                proxy=proxy,
                token_test=False,
                concurrency_test=True,
                concurrency_steps=config["test"]["concurrency_steps"],
                progress_callback=_make_progress_callback(),
            )
            _progress_tracker.done("done", results)
        except Exception as e:
            _progress_tracker.done("error", {"error": str(e)})

    _progress_tracker.start(total=0, status="loading")
    asyncio.create_task(_run())
    return {"message": "Concurrency test started", "status": "loading"}


@app.post("/api/test/concurrency/batch", tags=["Test"], include_in_schema=False)
async def api_test_concurrency_batch():
    """Run concurrency tests on specific keys (batch alias)."""
    return await api_test_concurrency()

# ---
# BALANCE
# ---

@app.post("/api/balance", tags=["Balance"], response_model=BalanceResponse)
async def api_balance(body: BalanceRequest):
    """Query account balance for a key."""
    key = (body.key or "").strip()
    provider_name = (body.provider or "").strip()

    custom_url = body.custom_base_url
    if custom_url:
        allowed_domains = get_allowed_domains(PROVIDERS)
        validate_custom_base_url(custom_url, allowed_domains)
        custom_base_url.set(custom_url)
    if not key:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message=t("VALIDATION_MISSING_KEY"),
        )

    try:
        if not provider_name:
            proxy = get_proxy(config.get("proxy")) or None
            async with httpx.AsyncClient(timeout=config["check"]["timeout_seconds"], proxy=proxy) as client:
                provider_name = await detect_provider(client, key)
            if not provider_name or provider_name == 'unknown':
                raise ValidationError(
                    code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                    message=t("VALIDATION_PROVIDER_UNKNOWN"),
                )

        provider_name_lower = provider_name.lower()
        provider_obj = PROVIDERS.get(provider_name_lower)
        if not provider_obj:
            raise ValidationError(
                code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN,
                message=t("VALIDATION_PROVIDER_UNKNOWN"),
            )

        proxy = get_proxy(config.get("proxy")) or None
        error = None
        balance_value = None
        currency = None
        supported = False

        if hasattr(provider_obj, "get_balance"):
            supported = True
            async with httpx.AsyncClient(
                timeout=config["check"]["timeout_seconds"],
                proxy=proxy,
            ) as client:
                try:
                    bal = await provider_obj.get_balance(client, key)
                    if bal.supported:
                        balance_value = bal.balance
                        currency = bal.currency
                    else:
                        supported = False
                    if bal.error:
                        error = bal.error
                except Exception as e:
                    error = str(e)
        else:
            error = "Provider does not support balance queries"

        project_logger.log_web_action("balance", f"{mask_key(key)} {provider_name}: {balance_value}")

        return BalanceResponse(
            provider=provider_name,
            supported=supported,
            balance=balance_value,
            currency=currency,
            key_masked=mask_key(key),
            error=error,
        )
    finally:
        custom_base_url.set(None)


# ---
# MODELS
# ---

@app.get("/api/models", tags=["Models"], response_model=ModelsResponse)
async def api_models(
    provider: str = Query(None, description="Provider name"),
    type_filter: str = Query("all", description="Model type filter"),
    key: str = Query(None, description="API key for live model fetch"),
):
    """Get available models for a provider (static or live)."""
    provider_name = (provider or "").lower()

    if not provider_name:
        # Try to detect provider from key if provided
        if key:
            proxy = get_proxy(config.get("proxy")) or None
            async with httpx.AsyncClient(
                timeout=config["check"]["timeout_seconds"],
                proxy=proxy,
            ) as client:
                detected = await detect_provider(client, key)
            if detected and detected != 'unknown' and detected in PROVIDERS:
                provider_name = detected
                provider_obj = PROVIDERS[provider_name]
                # Fall through to live model fetch below
            else:
                return ModelsResponse(
                    provider="unknown",
                    models=[],
                    total=0,
                    type_filter=type_filter,
                    source=None,
                    hint="未找到有效的 Key，请检查 Key 是否正确或 Provider 是否支持",
                )
        else:
            # No key provided, return all static models from PROVIDER_MODELS
            all_models: list[str] = []
            for provider_models in PROVIDER_MODELS.values():
                all_models.extend(provider_models)
            return ModelsResponse(
                provider="all",
                models=sorted(set(all_models)),
                total=len(set(all_models)),
                type_filter=type_filter,
                source="static",
            )

    provider_obj = PROVIDERS.get(provider_name)
    if not provider_obj:
        return ModelsResponse(
            provider=provider_name,
            models=[],
            total=0,
            type_filter=type_filter,
            source=None,
            hint="Provider not found",
        )

    models: list[str] = []
    source = "static"

    if key and hasattr(provider_obj, "get_models"):
        proxy = get_proxy(config.get("proxy")) or None
        async with httpx.AsyncClient(
            timeout=config["check"]["timeout_seconds"],
            proxy=proxy,
        ) as client:
            try:
                models = await provider_obj.get_models(client, key) or []
                source = "api"
            except Exception:
                pass

    if not models and hasattr(provider_obj, "models"):
        models = getattr(provider_obj, "models", [])
    
    # Fallback to static models from PROVIDER_MODELS (Cherry Studio sync)
    if not models:
        models = PROVIDER_MODELS.get(provider_name, [])
    # Apply type filter (if model_capabilities module is available)
    filtered = models
    try:
        from key_manager.model_capabilities import detector
        await detector.load()
        if type_filter == "vision":
            filtered = [m for m in models if detector.is_vision_model(m)]
        elif type_filter in ("tool", "tooluse"):
            filtered = [m for m in models if detector.is_tool_model(m)]
        elif type_filter == "websearch":
            filtered = [m for m in models if detector.is_websearch_model(m)]
        elif type_filter == "reasoning":
            filtered = [m for m in models if detector.is_reasoning_model(m)]
        elif type_filter == "embedding":
            filtered = [m for m in models if detector.is_embedding_model(m)]
        elif type_filter == "rerank":
            filtered = [m for m in models if detector.is_rerank_model(m)]
        elif type_filter == "free":
            filtered = [m for m in models if detector.is_free_model(m)]
    except Exception:
        pass

    return ModelsResponse(
        provider=provider_name,
        models=filtered,
        total=len(filtered),
        type_filter=type_filter,
        source=source,
    )


@app.get("/api/models/capabilities", tags=["Models"])
async def api_models_capabilities(
    models: str = Query(..., description="Comma-separated model IDs"),
):
    """Get capabilities for a list of model IDs."""
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    if not model_list:
        return {"capabilities": {}}
    
    try:
        from key_manager.model_capabilities import detector
        await detector.load()
        
        result = {}
        for model_id in model_list:
            result[model_id] = detector.get_model_capabilities(model_id)
        
        return {"capabilities": result}
    except Exception as e:
        return {"capabilities": {}, "error": str(e)}

@app.post("/api/models/check", tags=["Models"])
async def api_models_check(request: Request):
    """Live model availability check (SSE stream)."""
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body")

    provider_name = (body.get("provider") or "").lower()
    key = (body.get("key") or "").strip()
    if not key:
        raise ValidationError(code=ErrorCode.VALIDATION_MISSING_KEY, message=t("VALIDATION_MISSING_KEY"))

    proxy = get_proxy(config.get("proxy")) or None
    provider_obj = None
    models: list[str] = []
    source = "api"

    # Step 1: Find provider and get models
    if provider_name:
        provider_obj = PROVIDERS.get(provider_name)
        if provider_obj:
            async with httpx.AsyncClient(timeout=config["check"]["timeout_seconds"], proxy=proxy) as client:
                try:
                    models = await provider_obj.get_models(client, key) or []
                except Exception:
                    pass
    else:
        # Use detect_provider for robust auto-detection
        async with httpx.AsyncClient(timeout=config["check"]["timeout_seconds"], proxy=proxy) as client:
            detected = await detect_provider(client, key)
            if detected and detected != 'unknown':
                provider_name = detected
                provider_obj = PROVIDERS.get(provider_name)
                if provider_obj:
                    try:
                        models = await provider_obj.get_models(client, key) or []
                    except Exception:
                        pass

    # Step 2: Fallback to static models from PROVIDER_MODELS
    if not models and provider_obj:
        source = "static"
        models = PROVIDER_MODELS.get(provider_name, [])
    if not provider_name:
        candidates = detect_by_prefix(key)
        provider_name = candidates[0] if candidates else "unknown"
        provider_obj = PROVIDERS.get(provider_name)

    # Step 3: SSE response
    if not models:
        async def empty():
            yield f'data: {{"type":"complete","provider":"{provider_name}","available":0,"total":0,"source":"{source}"}}\n\n'
        return StreamingResponse(empty(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    async def stream():
        # Phase 1: Report models found
        yield f'data: {{"type":"progress","current":0,"total":{len(models)},"model":"","mode":"parallel"}}\n\n'

        # Phase 2: Check all models
        available_count = 0
        timeout_count = 0
        all_available_models = set()
        failed_models = []

        async def check_model(http, model):
            """Use provider's _probe_model method with 10s timeout."""
            try:
                result = await asyncio.wait_for(
                    provider_obj._probe_model(http, provider_obj.build_headers(key), model),
                    timeout=10.0
                )
                return model, 200 if result else -2
            except asyncio.TimeoutError:
                return model, -1
            except httpx.TimeoutException:
                return model, -1
            except Exception:
                return model, -2

        async with httpx.AsyncClient(proxy=proxy) as http:
            # Step 1: Parallel check with dynamic batch_size
            # Start from 5, +1 on each success, stay same on failure
            batch_size = 5
            i = 0
            while i < len(models):
                batch = models[i:i+batch_size]
                yield f'data: {{"type":"progress","current":{i+1},"total":{len(models)},"model":"{batch[0]}","mode":"parallel","batch_size":{len(batch)}}}\n\n'

                results = await asyncio.gather(*[check_model(http, m) for m in batch])

                batch_success = True
                for model, code in results:
                    if code == 200:
                        available_count += 1
                        all_available_models.add(model)
                        yield f'data: {{"type":"result","model":"{model}","available":true,"status":"available"}}\n\n'
                    else:
                        failed_models.append(model)
                        batch_success = False
                        yield f'data: {{"type":"model_timeout","model":"{model}"}}\n\n'

                # Adjust batch_size: +1 if all success, stay same if any failure
                if batch_success:
                    batch_size += 1
                i += len(batch)
            # Step 2: Serial retry failed models
            if failed_models:
                yield f'data: {{"type":"serial_mode","reason":"retry_failed"}}\n\n'
                await asyncio.sleep(0.5)

                for model in failed_models[:]:
                    if model in all_available_models:
                        continue

                    _, code = await check_model(http, model)

                    if code == 200:
                        available_count += 1
                        all_available_models.add(model)
                        failed_models.remove(model)
                        yield f'data: {{"type":"result","model":"{model}","available":true,"status":"available","retry":true}}\n\n'
                    else:
                        timeout_count += 1
                        yield f'data: {{"type":"model_timeout","model":"{model}","retry":true}}\n\n'

        # Final summary
        yield f'data: {{"type":"complete","provider":"{provider_name}","available":{available_count},"total":{len(models)},"timeout":{timeout_count},"source":"{source}"}}\n\n'

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","Connection":"keep-alive","X-Accel-Buffering":"no"})


# ---
# PROVIDERS
# ---

@app.get("/api/providers", tags=["Providers"], response_model=ProvidersResponse)
async def api_providers():
    """List all registered providers."""
    provider_list: list[ProviderInfoModel] = []
    for name, p in PROVIDERS.items():
        prefix = ""
        for pf, providers in KEY_PREFIX_MAP.items():
            if name in providers:
                prefix = pf
                break
        provider_list.append(ProviderInfoModel(
            name=name,
            display_name=get_display_name(name),
            prefix=prefix or "-",
            base_url=getattr(p, "base_url", ""),
            type="ai",
        ))
    return ProvidersResponse(providers=provider_list, total=len(provider_list))


@app.get("/api/providers/detail", tags=["Providers"], response_model=ProviderDetailResponse)
async def api_providers_detail():
    """Get detailed provider information including website and docs URLs."""
    detail_list: list[ProviderDetail] = []
    for name in PROVIDERS:
        website = PROVIDER_WEBSITES.get(name, {})
        prefix = ""
        for pf, providers in KEY_PREFIX_MAP.items():
            if name in providers:
                prefix = pf
                break
        detail_list.append(ProviderDetail(
            name=name,
            display_name=get_display_name(name),
            prefix=prefix or "-",
            base_url=getattr(PROVIDERS[name], "base_url", ""),
            website_url=website.get("url", ""),
            docs_url=website.get("docs", ""),
            website_name=website.get("name", get_display_name(name)),
        ))
    return ProviderDetailResponse(providers=detail_list, total=len(detail_list))


# ---
# STATS
# ---

@app.get("/api/stats", tags=["Stats"], response_model=StatsResponse)
async def api_stats():
    """Get key statistics broken down by provider."""
    data = _load_keys_data()
    keys_dict = data.get("keys", {})

    stats: dict[str, StatsProviderEntry] = {}
    total = 0

    for key, info in keys_dict.items():
        total += 1
        provider = info.get("provider", "unknown")
        status = info.get("status", "unknown")

        if provider not in stats:
            stats[provider] = StatsProviderEntry(
                total=0, valid=0, invalid=0, error=0,
                display_name=get_display_name(provider),
            )

        stats[provider].total += 1
        if status == "valid":
            stats[provider].valid += 1
        elif status == "invalid":
            stats[provider].invalid += 1
        else:
            stats[provider].error += 1

    return StatsResponse(
        providers=stats,
        total=total,
    )


@app.get("/api/stats/chart", tags=["Stats"], response_model=StatsChartResponse)
async def api_stats_chart():
    """Get chart data for key status distribution."""
    data = _load_keys_data()
    keys_dict = data.get("keys", {})

    providers: dict[str, StatsChartProviderEntry] = {}
    global_statuses = StatsChartStatuses()

    for key, info in keys_dict.items():
        provider = info.get("provider", "unknown")
        status = info.get("status", "unknown")

        if provider not in providers:
            providers[provider] = StatsChartProviderEntry(
                provider=provider,
                display_name=get_display_name(provider),
                statuses=StatsChartStatuses(),
            )

        if status == "valid":
            providers[provider].statuses.valid += 1
            providers[provider].valid += 1
            global_statuses.valid += 1
        elif status == "invalid":
            providers[provider].statuses.invalid += 1
            providers[provider].invalid += 1
            global_statuses.invalid += 1
        else:
            providers[provider].statuses.error += 1
            providers[provider].error += 1
            global_statuses.error += 1

        providers[provider].total += 1

    return StatsChartResponse(
        providers=list(providers.values()),
        statuses=global_statuses,
    )


# ---

@app.get("/api/proxy", tags=["Proxy"], response_model=ProxyResponse)
async def api_proxy():
    """Get proxy configuration status."""
    config_proxy = config.get("proxy")
    proxy = get_proxy(config_proxy)
    
    if proxy:
        # Check if it's from config or auto-detected
        if config_proxy is not None and config_proxy != "":
            source = "config"
        else:
            source = "auto"
    else:
        proxy = None
        source = "none"
    
    return ProxyResponse(proxy=proxy, source=source)
# LOGS
# ---

@app.get("/api/logs", tags=["Logs"], response_model=LogsResponse)
async def api_logs():
    """Get recent log entries."""
    logs = project_logger.get_recent_logs()
    return LogsResponse(logs=[LogEntry(message=log) if isinstance(log, str) else LogEntry(**log) for log in logs])


@app.get("/api/logs/operations", tags=["Logs"], response_model=OperationsResponse)
async def api_logs_operations():
    """Get recent operation log entries."""
    operations = project_logger.get_operations_log()
    return OperationsResponse(operations=[OperationEntry(**entry) for entry in operations])


# ---
# PROGRESS
# ---

@app.get("/api/progress", tags=["Progress"], response_model=ProgressResponse)
async def api_progress():
    """Get current progress of long-running operations."""
    return _progress_tracker.snapshot()


@app.get("/api/progress/stream", tags=["Progress"])
async def api_progress_stream():
    """Stream progress updates via SSE."""
    return StreamingResponse(
        _sse_progress_event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# Webhook routes

@app.get("/api/webhooks", tags=["Webhooks"])
async def api_webhooks_list():
    """List all configured webhooks."""
    return webhook_manager.list_all()


@app.post("/api/webhooks", tags=["Webhooks"])
async def api_webhooks_create(request: Request):
    """Create a new webhook."""
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body")
    webhook_id = webhook_manager.register(
        url=body.get('url', ''),
        events=body.get('events'),
        secret=body.get('secret'),
        active=body.get('active', True),
        max_retries=body.get('max_retries', 3),
    )
    return {"success": True, "webhook_id": webhook_id}


@app.get("/api/webhooks/{webhook_id}", tags=["Webhooks"])
async def api_webhooks_get(webhook_id: str):
    """Get a specific webhook."""
    webhook = webhook_manager.get(webhook_id)
    if not webhook:
        raise ValidationError(code=ErrorCode.VALIDATION_FILE_NOT_FOUND, message="Webhook not found")
    return webhook


@app.put("/api/webhooks/{webhook_id}", tags=["Webhooks"])
async def api_webhooks_update(webhook_id: str, request: Request):
    """Update a webhook."""
    try:
        body = await request.json()
    except Exception:
        raise ValidationError(code=ErrorCode.VALIDATION_INVALID_FORMAT, message="Invalid JSON body")
    webhook_manager.update(webhook_id, **body)
    return {"success": True}


@app.delete("/api/webhooks/{webhook_id}", tags=["Webhooks"])
async def api_webhooks_delete(webhook_id: str):
    """Delete a webhook."""
    webhook_manager.unregister(webhook_id)
    return {"success": True}


@app.get("/api/webhooks/log/deliveries", tags=["Webhooks"])
async def api_webhooks_log_deliveries():
    """Get webhook delivery logs."""
    return webhook_manager.get_delivery_log()


@app.delete("/api/webhooks/log/deliveries", tags=["Webhooks"])
async def api_webhooks_log_deliveries_clear():
    """Clear webhook delivery logs."""
    webhook_manager.clear_delivery_log()
    return {"success": True}


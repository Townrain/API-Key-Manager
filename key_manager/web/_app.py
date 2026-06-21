"""FastAPI application for API Key Manager.

Serves the web UI and REST API for managing API keys across 37+ providers.
"""

import asyncio
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import FastAPI, Request, Query, UploadFile, File, Form, Body
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

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
from key_manager.i18n import t
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

# Debug system (optional, for development)
DEBUG_ENABLED = False
debug_logger = None
FunctionTracer = None

try:
    from webdebug import init_debug, debug_logger, FunctionTracer
    DEBUG_ENABLED = True
except ImportError:
    pass
# FastAPI application

app = FastAPI(
    title="API Key Manager",
    description="Manage and validate API keys for 45+ AI providers. "
    "Import, check validity, test token limits and concurrency, "
    "query balances, and export working keys.",
    version="4.0.0",
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
    allow_origins=["http://localhost:18001", "http://127.0.0.1:18001", "http://localhost:3000", "http://127.0.0.1:3000"],
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

# Progress tracking (extracted to progress.py)
from key_manager.web.progress import (
    ProgressTracker,
    _progress_tracker,
    _make_progress_callback,
    _sse_progress_event_generator,
)

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


# Middleware and error handlers (extracted to middleware.py)
from key_manager.web.middleware import (
    _RATE_LIMIT_STORE,
    rate_limit_middleware,
    _AUTH_WHITELIST,
    auth_middleware,
    i18n_middleware,
    pydantic_validation_error_handler,
    key_manager_error_handler,
    validation_error_handler,
    setup_middleware,
    setup_error_handlers,
)

# Register middleware and error handlers
setup_middleware(app, config)
setup_error_handlers(app)

# ---
# WEB UI
# ---

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_TEMPLATES_DIR_ALT = Path(__file__).resolve().parent.parent / "templates"

if _TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
elif _TEMPLATES_DIR_ALT.exists():
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR_ALT))
else:
    templates = None

# Static files (CSS, JS extracted from inline)
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def web_ui(request: Request):
    """Serve the web UI."""
    if templates and (_TEMPLATES_DIR / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request})
    if templates and (_TEMPLATES_DIR_ALT / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request})
    return HTMLResponse("<html><body><h1>API Key Manager</h1><p>Web UI not found.</p></body></html>")


# ---
# Route modules (extracted to key_manager/web/routes/)
# ---

from key_manager.web.routes import (
    keys,
    check,
    test,
    balance,
    models,
    providers,
    stats,
    misc,
)

app.include_router(keys.router)
app.include_router(check.router)
app.include_router(test.router)
app.include_router(balance.router)
app.include_router(models.router)
app.include_router(providers.router)
app.include_router(stats.router)
app.include_router(misc.router)

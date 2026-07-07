"""FastAPI application for API Key Manager.

Serves the web UI and REST API for managing API keys across 37+ providers.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from key_manager.config import load_config
from key_manager.detector import detect_provider  # noqa: F401
from key_manager.errors import StorageError
from key_manager.logger import get_project_logger
from key_manager.parser import (
    import_keys,  # noqa: F401
    validate_import_path,  # noqa: F401
)
from key_manager.providers import PROVIDERS  # noqa: F401
from key_manager.storage import KeyStore
from key_manager.validator import validate_keys  # noqa: F401
from key_manager.web.middleware import (
    setup_error_handlers,
    setup_middleware,
)
from key_manager.web.routes import (
    balance,
    check,
    keys,
    misc,
    models,
    providers,
    stats,
    test,
)

# Module-level config

config = load_config()

# Debug system (optional, for development)
DEBUG_ENABLED = False
debug_logger = None
FunctionTracer = None

try:
    from webdebug import FunctionTracer, debug_logger, init_debug
    DEBUG_ENABLED = True
except ImportError:
    pass
# FastAPI application

app = FastAPI(
    title="API Key Manager",
    description="Manage and validate API keys for 45+ AI providers. "
    "Import, check validity, test token limits and concurrency, "
    "query balances, and export working keys.",
    version="5.0.1",
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:18001", "http://127.0.0.1:18001", "http://localhost:3000", "http://127.0.0.1:3000", "null"],
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

# Helper: load keys store

def _load_keys_store(config_override: dict | None = None) -> KeyStore:
    cfg = config_override or config
    return KeyStore(cfg["storage"]["keys_file"], cfg)


def _load_keys_data(config_override: dict | None = None) -> dict:
    cfg = config_override or config
    keys_path = Path(cfg["storage"]["keys_file"])
    if not keys_path.exists():
        return {"keys": {}}
    try:
        return _load_keys_store(cfg).load()
    except StorageError:
        raise
    except Exception as e:
        get_project_logger().main_logger.warning(f"Failed to load/decrypt keys data: {e}")
        # Return empty data structure for unexpected errors (e.g., corrupt JSON)
        return {"keys": {}}


def _save_keys_data(data: dict, config_override: dict | None = None):
    cfg = config_override or config
    _load_keys_store(cfg).save(data)


# Middleware and error handlers (extracted to middleware.py)

# Register middleware and error handlers
setup_middleware(app, config)
setup_error_handlers(app)

# ---
# WEB UI
# ---

_TAURI_DIR = Path(__file__).resolve().parent.parent.parent / "static_tauri"
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
_TEMPLATES_DIR_ALT = Path(__file__).resolve().parent.parent / "templates"

# Tauri React SPA: mount assets at /assets
if (_TAURI_DIR / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_TAURI_DIR / "assets")), name="tauri_assets")

# Legacy static files
_STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"
if _STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# Jinja2 templates (legacy fallback)
if _TEMPLATES_DIR.exists():
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
elif _TEMPLATES_DIR_ALT.exists():
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR_ALT))
else:
    templates = None


@app.get("/", include_in_schema=False)
async def web_ui(request: Request):
    """Serve the web UI with API token injected."""
    api_token = ""
    try:
        from key_manager.storage import derive_api_token
        api_token = derive_api_token(config)
    except Exception:
        pass

    # Tauri React SPA (preferred)
    tauri_index = _TAURI_DIR / "index.html"
    if tauri_index.exists():
        html = tauri_index.read_text(encoding="utf-8")
        html = html.replace("<title>tauri-compare</title>", "<title>KeyHub</title>")
        html = html.replace("</head>", f"<script>window.__API_TOKEN__ = '{api_token}';</script></head>")
        return HTMLResponse(html)

    # Legacy Jinja2 template fallback
    if templates and (_TEMPLATES_DIR / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request, "api_token": api_token})
    if templates and (_TEMPLATES_DIR_ALT / "index.html").exists():
        return templates.TemplateResponse("index.html", {"request": request, "api_token": api_token})
    return HTMLResponse("<html><body><h1>API Key Manager</h1><p>Web UI not found.</p></body></html>")

# ---
# Route modules (extracted to key_manager/web/routes/)
# ---

# Route modules (extracted to key_manager/web/routes/)

app.include_router(keys.router)
app.include_router(check.router)
app.include_router(test.router)
app.include_router(balance.router)
app.include_router(models.router)
app.include_router(providers.router)
app.include_router(stats.router)
app.include_router(misc.router)

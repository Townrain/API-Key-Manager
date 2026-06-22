"""Middleware and error handlers for the FastAPI application.

Provides rate limiting, authentication, i18n, and structured error responses.
"""

import hmac
import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from key_manager.errors import (
    ErrorCode,
    ErrorResponse,
    KeyManagerError,
    ValidationError,
)
from key_manager.i18n import get_lang_from_header, set_lang, t

logger = logging.getLogger(__name__)

# Module-level config reference, set by setup_middleware()
_config: dict | None = None

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

_RATE_LIMIT_STORE: dict[str, list[float]] = {}
_RATE_LIMIT_LAST_CLEANUP: float = 0.0




def _cleanup_rate_limit_store():
    """Clean up old entries from rate limit store to prevent memory leak."""
    global _RATE_LIMIT_LAST_CLEANUP
    now = time.time()
    # Only cleanup every 60 seconds
    if now - _RATE_LIMIT_LAST_CLEANUP < 60.0:
        return
    _RATE_LIMIT_LAST_CLEANUP = now
    # Remove IPs with no recent activity (older than 5 minutes)
    cutoff = now - 300.0
    ips_to_remove = []
    for ip, timestamps in _RATE_LIMIT_STORE.items():
        # Remove old timestamps
        _RATE_LIMIT_STORE[ip] = [t for t in timestamps if now - t < 300.0]
        # If no recent timestamps, mark for removal
        if not _RATE_LIMIT_STORE[ip]:
            ips_to_remove.append(ip)
    # Remove empty IPs
    for ip in ips_to_remove:
        del _RATE_LIMIT_STORE[ip]

async def rate_limit_middleware(request: Request, call_next):
    """Rate limit requests by client IP."""
    # Cleanup old entries periodically
    _cleanup_rate_limit_store()

    # Skip for static/docs and auth whitelist
    if request.url.path in _AUTH_WHITELIST or request.url.path.startswith("/static"):
        return await call_next(request)

    cfg = _config or {}
    rate_limit_config = cfg.get("rate_limit", {})
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


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

_AUTH_WHITELIST = {"/", "/docs", "/redoc", "/openapi.json"}


async def auth_middleware(request: Request, call_next):
    """Authenticate requests via Bearer token."""
    cfg = _config or {}
    api_key = cfg.get("auth", {}).get("api_key", "") or os.environ.get("KEY_MANAGER_API_KEY", "")
    if not api_key:
        # Log warning once at startup (not on every request)
        app = request.app
        if not hasattr(app, '_auth_warning_logged'):
            logger.warning(
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


# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------


async def i18n_middleware(request: Request, call_next):
    """Set language from Accept-Language header."""
    lang = get_lang_from_header(request.headers.get("accept-language"))
    set_lang(lang)
    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


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


async def key_manager_error_handler(request: Request, exc: KeyManagerError):
    status_code, body = exc.to_response()
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def validation_error_handler(request: Request, exc: ValidationError):
    status_code, body = exc.to_response()
    return JSONResponse(status_code=status_code, content=body.model_dump())


# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def setup_middleware(app: FastAPI, config: dict) -> None:
    """Register all middleware on the given FastAPI app."""
    global _config
    _config = config

    app.middleware("http")(rate_limit_middleware)
    app.middleware("http")(auth_middleware)
    app.middleware("http")(i18n_middleware)


def setup_error_handlers(app: FastAPI) -> None:
    """Register all error handlers on the given FastAPI app."""
    app.exception_handler(RequestValidationError)(pydantic_validation_error_handler)
    app.exception_handler(KeyManagerError)(key_manager_error_handler)
    app.exception_handler(ValidationError)(validation_error_handler)

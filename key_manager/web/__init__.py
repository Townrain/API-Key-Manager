"""API Key Manager web package.

This package provides the FastAPI application for the API Key Manager.
All public names from the original web module are re-exported here
for backward compatibility.
"""

# Explicit exports for IDE type checking
__all__ = [
    "app",
    "config",
    "auth_middleware",
    "i18n_middleware",
    "rate_limit_middleware",
    "setup_middleware",
    "setup_error_handlers",
    "ProgressTracker",
]
from key_manager.web._app import (  # noqa: F401
    app,
    config,
)
from key_manager.web.middleware import (  # noqa: F401
    _AUTH_WHITELIST,
    _RATE_LIMIT_STORE,
    auth_middleware,  # noqa: F401
    i18n_middleware,
    key_manager_error_handler,
    pydantic_validation_error_handler,
    rate_limit_middleware,
    setup_error_handlers,
    setup_middleware,
    validation_error_handler,
)
from key_manager.web.middleware import (
    auth_middleware as auth_middleware_func,  # noqa: F401
)

# Re-export from submodules for direct access
from key_manager.web.progress import (  # noqa: F401
    ProgressTracker,
    _make_progress_callback,
    _sse_progress_event_generator,
)
from key_manager.web.progress import (
    _progress_tracker as _progress_tracker_singleton,  # noqa: F401
)

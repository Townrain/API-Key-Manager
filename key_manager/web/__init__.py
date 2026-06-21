"""API Key Manager web package.

This package provides the FastAPI application for the API Key Manager.
All public names from the original web module are re-exported here
for backward compatibility.
"""
from key_manager.web._app import *  # noqa: F401, F403
from key_manager.web._app import (  # noqa: F401
    app,
    config,
    _progress_tracker,
    auth_middleware,
)

# Re-export from submodules for direct access
from key_manager.web.progress import (  # noqa: F401
    ProgressTracker,
    _progress_tracker as _progress_tracker_singleton,
    _make_progress_callback,
    _sse_progress_event_generator,
)
from key_manager.web.middleware import (  # noqa: F401
    _RATE_LIMIT_STORE,
    rate_limit_middleware,
    _AUTH_WHITELIST,
    auth_middleware as auth_middleware_func,
    i18n_middleware,
    pydantic_validation_error_handler,
    key_manager_error_handler,
    validation_error_handler,
    setup_middleware,
    setup_error_handlers,
)

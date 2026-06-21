"""Route modules for the API Key Manager.

Adding New Routes
-----------------
1. Create a new module in this directory (e.g., ``my_feature.py``).
2. Define an ``APIRouter`` with appropriate tags.
3. Register the router in ``key_manager/web/_app.py`` via ``app.include_router()``.
4. Add Pydantic models to ``key_manager/api_models.py`` if needed.

Adding Middleware
-----------------
1. Add middleware function to ``key_manager/web/middleware.py``.
2. Register it in ``setup_middleware()``.

Adding Error Handlers
---------------------
1. Add handler to ``key_manager/web/middleware.py``.
2. Register it in ``setup_error_handlers()``.
"""

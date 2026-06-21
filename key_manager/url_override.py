from contextvars import ContextVar

# Per-request override for provider base URL.
# Set in web.py before calling provider methods; providers read via get_base_url().
custom_base_url: ContextVar[str | None] = ContextVar('custom_base_url', default=None)

"""Custom exceptions for API Key Manager SDK."""

from __future__ import annotations
from typing import Any, Optional


class KeyManagerError(Exception):
    """Base exception for Key Manager SDK."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AuthenticationError(KeyManagerError):
    """Raised when authentication fails."""


class NotFoundError(KeyManagerError):
    """Raised when a resource is not found."""


class ValidationError(KeyManagerError):
    """Raised when request validation fails."""

    def __init__(self, message: str, errors: Optional[list[dict]] = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.errors = errors or []


class RateLimitError(KeyManagerError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(KeyManagerError):
    """Raised on 5xx server errors."""


class ConnectionError(KeyManagerError):
    """Raised when connection to server fails."""

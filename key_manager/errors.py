from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(str, Enum):
    """Structured error codes for the API Key Manager."""

    # Validation errors (1xxx)
    VALIDATION_MISSING_KEY = "VALIDATION_MISSING_KEY"
    VALIDATION_INVALID_FORMAT = "VALIDATION_INVALID_FORMAT"
    VALIDATION_PROVIDER_UNKNOWN = "VALIDATION_PROVIDER_UNKNOWN"
    VALIDATION_FILE_NOT_FOUND = "VALIDATION_FILE_NOT_FOUND"
    VALIDATION_FILE_FORMAT = "VALIDATION_FILE_FORMAT"
    VALIDATION_KEY_NOT_FOUND = "VALIDATION_KEY_NOT_FOUND"

    # Storage errors (2xxx)
    STORAGE_READ_ERROR = "STORAGE_READ_ERROR"
    STORAGE_WRITE_ERROR = "STORAGE_WRITE_ERROR"
    STORAGE_ENCRYPTION_ERROR = "STORAGE_ENCRYPTION_ERROR"
    STORAGE_MIGRATION_ERROR = "STORAGE_MIGRATION_ERROR"

    # Provider errors (3xxx)
    PROVIDER_CHECK_FAILED = "PROVIDER_CHECK_FAILED"
    PROVIDER_NOT_SUPPORTED = "PROVIDER_NOT_SUPPORTED"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"

    # System errors (4xxx)
    SYSTEM_INTERNAL_ERROR = "SYSTEM_INTERNAL_ERROR"
    SYSTEM_PROGRESS_CONFLICT = "SYSTEM_PROGRESS_CONFLICT"

    # Auth errors (5xxx)
    AUTH_REQUIRED = "AUTH_REQUIRED"


# Default HTTP status codes for each error code
ERROR_STATUS_CODES: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_MISSING_KEY: 400,
    ErrorCode.VALIDATION_INVALID_FORMAT: 400,
    ErrorCode.VALIDATION_PROVIDER_UNKNOWN: 400,
    ErrorCode.VALIDATION_FILE_NOT_FOUND: 404,
    ErrorCode.VALIDATION_FILE_FORMAT: 400,
    ErrorCode.VALIDATION_KEY_NOT_FOUND: 404,
    ErrorCode.STORAGE_READ_ERROR: 500,
    ErrorCode.STORAGE_WRITE_ERROR: 500,
    ErrorCode.STORAGE_ENCRYPTION_ERROR: 500,
    ErrorCode.STORAGE_MIGRATION_ERROR: 500,
    ErrorCode.PROVIDER_CHECK_FAILED: 502,
    ErrorCode.PROVIDER_NOT_SUPPORTED: 400,
    ErrorCode.PROVIDER_RATE_LIMITED: 429,
    ErrorCode.SYSTEM_INTERNAL_ERROR: 500,
    ErrorCode.SYSTEM_PROGRESS_CONFLICT: 409,
    ErrorCode.AUTH_REQUIRED: 401,
}

# Default human-readable messages for each error code
DEFAULT_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.VALIDATION_MISSING_KEY: "API key is required",
    ErrorCode.VALIDATION_INVALID_FORMAT: "API key format is invalid",
    ErrorCode.VALIDATION_PROVIDER_UNKNOWN: "Unable to detect provider, please select manually",
    ErrorCode.VALIDATION_FILE_NOT_FOUND: "File not found",
    ErrorCode.VALIDATION_FILE_FORMAT: "Unsupported file format",
    ErrorCode.VALIDATION_KEY_NOT_FOUND: "Key not found",
    ErrorCode.STORAGE_READ_ERROR: "Failed to read from storage",
    ErrorCode.STORAGE_WRITE_ERROR: "Failed to write to storage",
    ErrorCode.STORAGE_ENCRYPTION_ERROR: "Encryption/decryption operation failed",
    ErrorCode.STORAGE_MIGRATION_ERROR: "Data migration failed",
    ErrorCode.PROVIDER_CHECK_FAILED: "Provider key check failed",
    ErrorCode.PROVIDER_NOT_SUPPORTED: "Provider is not supported",
    ErrorCode.PROVIDER_RATE_LIMITED: "Provider rate limit exceeded",
    ErrorCode.SYSTEM_INTERNAL_ERROR: "Internal server error",
    ErrorCode.SYSTEM_PROGRESS_CONFLICT: "Another operation is already in progress",
    ErrorCode.AUTH_REQUIRED: "Authentication required",
}


class ErrorDetail(BaseModel):
    """Error detail embedded in ErrorResponse."""

    code: ErrorCode
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    """Standard error response envelope.

    JSON shape: {"error": {"code": "...", "message": "...", "details": {...}}}
    """

    error: ErrorDetail

    @classmethod
    def error_factory(
        cls,
        code: ErrorCode,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> "ErrorResponse":
        return cls(
            error=ErrorDetail(
                code=code,
                message=message or DEFAULT_MESSAGES.get(code, code.value),
                details=details or {},
            )
        )


class KeyManagerError(Exception):
    """Base exception for all API Key Manager errors."""

    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message or DEFAULT_MESSAGES.get(code, code.value)
        self.details = details or {}
        super().__init__(self.message)

    def to_response(self, status_code: int | None = None) -> tuple[int, ErrorResponse]:
        """Convert to HTTP status code and ErrorResponse body."""
        http_code = status_code or ERROR_STATUS_CODES.get(self.code, 500)
        body = ErrorResponse(
            error=ErrorDetail(
                code=self.code,
                message=self.message,
                details=self.details,
            )
        )
        return http_code, body


class ValidationError(KeyManagerError):
    """Raised for input validation failures."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.VALIDATION_MISSING_KEY,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, details=details)


class StorageError(KeyManagerError):
    """Raised for storage read/write/encryption failures."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.STORAGE_READ_ERROR,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, details=details)


class ProviderError(KeyManagerError):
    """Raised for provider interaction failures."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.PROVIDER_CHECK_FAILED,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, details=details)


class SystemError(KeyManagerError):
    """Raised for internal system errors."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.SYSTEM_INTERNAL_ERROR,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, details=details)

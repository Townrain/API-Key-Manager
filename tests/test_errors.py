import pytest

from key_manager.errors import (
    DEFAULT_MESSAGES,
    ERROR_STATUS_CODES,
    ErrorCode,
    ErrorResponse,
    KeyManagerError,
    ProviderError,
    StorageError,
    SystemError,
    ValidationError,
)


class TestErrorCode:
    def test_all_codes_present(self):
        expected = {
            "VALIDATION_MISSING_KEY",
            "VALIDATION_INVALID_FORMAT",
            "VALIDATION_PROVIDER_UNKNOWN",
            "VALIDATION_FILE_NOT_FOUND",
            "VALIDATION_FILE_FORMAT",
            "STORAGE_READ_ERROR",
            "STORAGE_WRITE_ERROR",
            "STORAGE_ENCRYPTION_ERROR",
            "STORAGE_MIGRATION_ERROR",
            "PROVIDER_CHECK_FAILED",
            "PROVIDER_NOT_SUPPORTED",
            "PROVIDER_RATE_LIMITED",
            "SYSTEM_INTERNAL_ERROR",
            "SYSTEM_PROGRESS_CONFLICT",
            "AUTH_REQUIRED",
            "VALIDATION_KEY_NOT_FOUND",
        }
        actual = {code.value for code in ErrorCode}
        assert actual == expected

    def test_enum_is_str(self):
        assert isinstance(ErrorCode.VALIDATION_MISSING_KEY, str)
        assert ErrorCode.VALIDATION_MISSING_KEY == "VALIDATION_MISSING_KEY"


class TestKeyManagerError:
    def test_default_message(self):
        err = KeyManagerError(code=ErrorCode.VALIDATION_MISSING_KEY)
        assert err.message == "API key is required"
        assert str(err) == "API key is required"

    def test_custom_message(self):
        err = KeyManagerError(
            code=ErrorCode.STORAGE_READ_ERROR,
            message="Custom read failure",
        )
        assert err.message == "Custom read failure"

    def test_details_preserved(self):
        details = {"path": "/data/keys.json", "reason": "permission denied"}
        err = KeyManagerError(code=ErrorCode.STORAGE_READ_ERROR, details=details)
        assert err.details == details

    def test_to_response(self):
        err = KeyManagerError(code=ErrorCode.VALIDATION_INVALID_FORMAT)
        status, body = err.to_response()
        assert status == 400
        assert body.error.code == ErrorCode.VALIDATION_INVALID_FORMAT
        assert body.error.message == "API key format is invalid"
        assert body.error.details == {}

    def test_to_response_with_details(self):
        details = {"field": "key", "value": "bad"}
        err = KeyManagerError(
            code=ErrorCode.VALIDATION_INVALID_FORMAT,
            details=details,
        )
        status, body = err.to_response()
        assert body.error.details == details

    def test_to_response_custom_status(self):
        err = KeyManagerError(code=ErrorCode.SYSTEM_INTERNAL_ERROR)
        status, _ = err.to_response(status_code=503)
        assert status == 503


class TestSubclasses:
    def test_validation_error_defaults(self):
        err = ValidationError()
        assert err.code == ErrorCode.VALIDATION_MISSING_KEY
        assert isinstance(err, KeyManagerError)

    def test_validation_error_custom_code(self):
        err = ValidationError(code=ErrorCode.VALIDATION_PROVIDER_UNKNOWN)
        assert err.code == ErrorCode.VALIDATION_PROVIDER_UNKNOWN

    def test_storage_error_defaults(self):
        err = StorageError()
        assert err.code == ErrorCode.STORAGE_READ_ERROR
        assert isinstance(err, KeyManagerError)

    def test_storage_error_custom_code(self):
        err = StorageError(code=ErrorCode.STORAGE_ENCRYPTION_ERROR, message="decryption failed")
        assert err.code == ErrorCode.STORAGE_ENCRYPTION_ERROR
        assert err.message == "decryption failed"

    def test_provider_error_defaults(self):
        err = ProviderError()
        assert err.code == ErrorCode.PROVIDER_CHECK_FAILED
        assert isinstance(err, KeyManagerError)

    def test_provider_error_rate_limited(self):
        err = ProviderError(
            code=ErrorCode.PROVIDER_RATE_LIMITED,
            message="429 Too Many Requests",
            details={"retry_after": 60},
        )
        assert err.code == ErrorCode.PROVIDER_RATE_LIMITED
        status, body = err.to_response()
        assert status == 429
        assert body.error.details["retry_after"] == 60

    def test_system_error_defaults(self):
        err = SystemError()
        assert err.code == ErrorCode.SYSTEM_INTERNAL_ERROR
        assert isinstance(err, KeyManagerError)

    def test_system_error_progress_conflict(self):
        err = SystemError(code=ErrorCode.SYSTEM_PROGRESS_CONFLICT)
        status, body = err.to_response()
        assert status == 409
        assert body.error.code == ErrorCode.SYSTEM_PROGRESS_CONFLICT


class TestErrorResponseSerialization:
    def test_json_shape(self):
        resp = ErrorResponse.error_factory(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message="key required",
            details={"field": "key"},
        )
        data = resp.model_dump()
        assert data == {
            "error": {
                "code": "VALIDATION_MISSING_KEY",
                "message": "key required",
                "details": {"field": "key"},
            }
        }

    def test_json_shape_empty_details(self):
        resp = ErrorResponse.error_factory(
            code=ErrorCode.SYSTEM_INTERNAL_ERROR,
        )
        data = resp.model_dump()
        assert data["error"]["details"] == {}

    def test_from_key_manager_error(self):
        err = StorageError(
            code=ErrorCode.STORAGE_WRITE_ERROR,
            message="disk full",
            details={"available_bytes": 0},
        )
        _, body = err.to_response()
        data = body.model_dump()
        assert data["error"]["code"] == "STORAGE_WRITE_ERROR"
        assert data["error"]["message"] == "disk full"
        assert data["error"]["details"]["available_bytes"] == 0


class TestStatusCodes:
    def test_all_codes_have_status(self):
        for code in ErrorCode:
            assert code in ERROR_STATUS_CODES, f"{code} missing from ERROR_STATUS_CODES"

    def test_all_codes_have_message(self):
        for code in ErrorCode:
            assert code in DEFAULT_MESSAGES, f"{code} missing from DEFAULT_MESSAGES"

    def test_validation_codes_are_4xx(self):
        for code in ErrorCode:
            if code.value.startswith("VALIDATION_"):
                assert 400 <= ERROR_STATUS_CODES[code] < 500

    def test_storage_codes_are_5xx(self):
        for code in ErrorCode:
            if code.value.startswith("STORAGE_"):
                assert ERROR_STATUS_CODES[code] == 500

"""Tests for all recent bug fixes: webhook, SSRF, unicode, validator, storage, proxy, auth."""

import hmac
import re
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestWebhookMethodNames:
    """Verify webhook route method names match WebhookManager API."""

    def test_webhook_manager_has_required_methods(self):
        """WebhookManager must have all methods called by web.py routes."""
        from key_manager.webhook import WebhookManager

        required_methods = [
            "list_all",
            "register",
            "get",
            "update",
            "unregister",
            "get_delivery_log",
            "clear_delivery_log",
        ]
        for method in required_methods:
            assert hasattr(WebhookManager, method), f"Missing method: {method}"

    def test_web_py_uses_correct_method_names(self):
        """web.py must call correct WebhookManager methods, not old names."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        # These old method names should NOT appear
        old_methods = [
            "list_webhooks",
            "add_webhook",
            "get_webhook",
            "update_webhook",
            "delete_webhook",
            "get_delivery_logs",
            "clear_delivery_logs",
        ]
        for method in old_methods:
            assert method not in content, f"Old method name found: {method}"

    def test_web_py_calls_correct_methods(self):
        """web.py must call correct WebhookManager methods."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        correct_methods = [
            "webhook_manager.list_all",
            "webhook_manager.register",
            "webhook_manager.get(",
            "webhook_manager.update",
            "webhook_manager.unregister",
            "webhook_manager.get_delivery_log",
            "webhook_manager.clear_delivery_log",
        ]
        for method in correct_methods:
            assert method in content, f"Correct method name missing: {method}"


class TestSSRFValidationWiredUp:
    """Verify SSRF validation is connected to web endpoints."""

    def test_ssrf_imports_in_web_py(self):
        """web.py should import SSRF validation functions."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        assert "validate_custom_base_url" in content
        assert "get_allowed_domains" in content
        assert "from key_manager.ssrf import" in content
        assert "from key_manager.url_override import custom_base_url" in content

    def test_check_single_validates_custom_url(self):
        """check/single endpoint should validate custom_base_url."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        # Find the check_single function
        match = re.search(
            r"async def api_check_single.*?(?=\n@|\Z)",
            content,
            re.DOTALL,
        )
        assert match, "api_check_single function not found"

        func_body = match.group(0)
        assert "validate_custom_base_url" in func_body
        assert "custom_base_url.set" in func_body
        assert "finally" in func_body
        assert "custom_base_url.set(None)" in func_body

    def test_balance_validates_custom_url(self):
        """balance endpoint should validate custom_base_url."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        # Find the balance function
        match = re.search(
            r"async def api_balance.*?(?=\n@|\Z)",
            content,
            re.DOTALL,
        )
        assert match, "api_balance function not found"

        func_body = match.group(0)
        assert "validate_custom_base_url" in func_body
        assert "custom_base_url.set" in func_body
        assert "finally" in func_body
        assert "custom_base_url.set(None)" in func_body


class TestUnicodeCleanup:
    """Verify unicode garbage is removed from web.py."""

    def test_no_unicode_garbage(self):
        """web.py should not contain unicode garbage patterns."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        garbage_patterns = ["芒聲聬", "芒聰聙", "忙聴聽", "忙鲁聲", "盲禄", "猫聡陋", "氓聤篓"]
        for pattern in garbage_patterns:
            assert pattern not in content, f"Unicode garbage found: {pattern}"

    def test_section_headers_are_clean(self):
        """Section headers in web.py should be clean ASCII or readable text."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        clean_headers = [
            "# Module-level config",
            "# Debug system",
            "# FastAPI application",
            "# Initialize debug system",
            "# Global progress tracker",
            "# SSE helpers",
            "# Helper: load keys store",
            "# Middleware: rate limit by IP",
            "# Middleware: authenticate requests via Bearer token",
            "# Middleware: set language from Accept-Language header",
            "# Error handlers",
            "# Webhook routes",
        ]
        for header in clean_headers:
            assert header in content, f"Clean header missing: {header}"


class TestValidatorImportFix:
    """Verify validator.py uses correct import path."""

    def test_validator_imports_from_key_manager(self):
        """validator.py should import from key_manager, not src."""
        validator_py = Path(__file__).parent.parent / "key_manager" / "validator.py"
        content = validator_py.read_text(encoding="utf-8")

        # Should NOT have src.providers.base
        assert "from src.providers.base" not in content
        # Should have key_manager.providers.base
        assert "from key_manager.providers.base import CheckResult" in content


class TestStorageErrorConsistency:
    """Verify StorageError is consistent across the codebase."""

    def test_storage_imports_from_errors(self):
        """storage.py should import StorageError from errors.py."""
        storage_py = Path(__file__).parent.parent / "key_manager" / "storage.py"
        content = storage_py.read_text(encoding="utf-8")

        assert "from key_manager.errors import ErrorCode, StorageError" in content

    def test_storage_no_duplicate_class(self):
        """storage.py should not define its own StorageError class."""
        storage_py = Path(__file__).parent.parent / "key_manager" / "storage.py"
        content = storage_py.read_text(encoding="utf-8")

        assert "class StorageError" not in content

    def test_storage_uses_error_code(self):
        """storage.py should use ErrorCode when raising StorageError."""
        storage_py = Path(__file__).parent.parent / "key_manager" / "storage.py"
        content = storage_py.read_text(encoding="utf-8")

        # All raise StorageError should use ErrorCode
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "raise StorageError(" in line:
                # Check if next few lines have ErrorCode
                context = "\n".join(lines[i:i+3])
                assert "ErrorCode." in context, f"Line {i+1}: StorageError without ErrorCode"


class TestProxyDeadCode:
    """Verify proxy.py has no dead code."""

    def test_proxy_has_single_get_proxy(self):
        """proxy.py should have exactly one get_proxy function definition."""
        proxy_py = Path(__file__).parent.parent / "key_manager" / "proxy.py"
        content = proxy_py.read_text(encoding="utf-8")

        # Count function definitions
        count = content.count("def get_proxy(")
        assert count == 1, f"Expected 1 get_proxy definition, found {count}"

    def test_proxy_no_unreachable_code(self):
        """proxy.py should not have dead code (duplicate function definitions)."""
        proxy_py = Path(__file__).parent.parent / "key_manager" / "proxy.py"
        content = proxy_py.read_text(encoding="utf-8")

        # Count get_proxy function definitions
        func_count = content.count("def get_proxy(")
        assert func_count == 1, f"Expected 1 get_proxy, found {func_count}"

        # Verify file is clean (no duplicate function bodies)
        assert "config_proxy" in content
        assert content.count("return config_proxy") == 1

class TestAuthTimingAttack:
    """Verify auth middleware uses constant-time comparison."""

    def test_auth_uses_hmac_compare(self):
        """Auth middleware should use hmac.compare_digest() for timing safety."""
        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        # Should import hmac
        assert "import hmac" in content

        # Find auth middleware
        match = re.search(
            r"async def auth_middleware.*?(?=\n@|\Z)",
            content,
            re.DOTALL,
        )
        assert match, "auth_middleware function not found"

        func_body = match.group(0)
        # Should use hmac.compare_digest
        assert "hmac.compare_digest" in func_body
        # Should NOT use == for auth comparison
        assert 'auth_header == f"Bearer' not in func_body

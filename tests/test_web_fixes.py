"""Tests for recent fixes: webhook method names, SSRF validation, unicode cleanup."""

import re

import pytest


class TestWebhookMethodNames:
    """Verify webhook route method names match WebhookManager API."""

    def test_web_py_imports_webhook_manager(self):
        """web.py should import webhook_manager."""
        from key_manager.web import webhook_manager
        assert webhook_manager is not None

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
        from pathlib import Path

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

        # These correct method names SHOULD appear
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
        from pathlib import Path

        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        assert "validate_custom_base_url" in content
        assert "get_allowed_domains" in content
        assert "from key_manager.ssrf import" in content
        assert "from key_manager.url_override import custom_base_url" in content

    def test_check_single_validates_custom_url(self):
        """check/single endpoint should validate custom_base_url."""
        from pathlib import Path

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
        from pathlib import Path

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
        from pathlib import Path

        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        garbage_patterns = ["芒聲聬", "芒聰聙", "忙聴聽", "忙鲁聲", "盲禄", "猫聡陋", "氓聤篓"]
        for pattern in garbage_patterns:
            assert pattern not in content, f"Unicode garbage found: {pattern}"

    def test_section_headers_are_clean(self):
        """Section headers in web.py should be clean ASCII or readable text."""
        from pathlib import Path

        web_py = Path(__file__).parent.parent / "key_manager" / "web.py"
        content = web_py.read_text(encoding="utf-8")

        # Check that section headers exist and are readable
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

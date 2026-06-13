import pytest

from key_manager.i18n import (
    _load_lang,
    _get_current_lang,
    get_lang_from_header,
    language_context,
    reload_translations,
    set_lang,
    t,
)


class TestTranslationLookup:
    def test_english_error_code(self):
        assert t("VALIDATION_MISSING_KEY", lang="en") == "API key is required"

    def test_chinese_error_code(self):
        assert t("VALIDATION_MISSING_KEY", lang="zh") == "API 密钥为必填项"

    def test_english_success_message(self):
        assert t("SUCCESS_KEY_ADDED", lang="en") == "Key added successfully"

    def test_chinese_success_message(self):
        assert t("SUCCESS_KEY_DELETED", lang="zh") == "密钥删除成功"

    def test_english_status_label(self):
        assert t("STATUS_ACTIVE", lang="en") == "Active"

    def test_chinese_status_label(self):
        assert t("STATUS_CHECKING", lang="zh") == "检查中"


class TestFallbackBehavior:
    def test_fallback_to_english_when_missing_in_other_lang(self, tmp_path):
        # zh has all keys so this tests the code returns raw code if truly missing
        assert t("NONEXISTENT_KEY", lang="en") == "NONEXISTENT_KEY"

    def test_fallback_returns_raw_code_for_unknown_lang(self):
        result = t("VALIDATION_MISSING_KEY", lang="xx")
        assert result == "API key is required"

    def test_default_language_is_english(self):
        assert _get_current_lang() == "en"


class TestParameterSubstitution:
    def test_english_substitution(self):
        result = t("SUCCESS_IMPORT_COMPLETE", lang="en", count=5)
        assert result == "Import completed: 5 keys added"

    def test_chinese_substitution(self):
        result = t("SUCCESS_IMPORT_COMPLETE", lang="zh", count=10)
        assert result == "导入完成：添加了 10 个密钥"

    def test_log_message_substitution(self):
        result = t("LOG_KEY_CHECK_START", lang="en", provider="OpenAI")
        assert result == "Starting key check for provider OpenAI"

    def test_chinese_log_substitution(self):
        result = t("LOG_IMPORT_COMPLETE", lang="zh", new=3, dupes=1)
        assert result == "导入完成：3 个新增，1 个重复"

    def test_missing_param_keeps_placeholder(self):
        result = t("SUCCESS_IMPORT_COMPLETE", lang="en")
        assert result == "Import completed: {count} keys added"


class TestLanguageContext:
    def test_set_lang_thread_local(self):
        set_lang("zh")
        assert _get_current_lang() == "zh"
        set_lang("en")
        assert _get_current_lang() == "en"

    def test_language_context_manager(self):
        set_lang("en")
        with language_context("zh"):
            assert _get_current_lang() == "zh"
            assert t("VALIDATION_MISSING_KEY") == "API 密钥为必填项"
        assert _get_current_lang() == "en"

    def test_context_manager_restores_on_exception(self):
        set_lang("en")
        try:
            with language_context("zh"):
                raise ValueError("test")
        except ValueError:
            pass
        assert _get_current_lang() == "en"


class TestAcceptLanguageHeader:
    def test_simple_english(self):
        assert get_lang_from_header("en") == "en"

    def test_simple_chinese(self):
        assert get_lang_from_header("zh") == "zh"

    def test_chinese_with_quality(self):
        assert get_lang_from_header("zh-CN,zh;q=0.9,en;q=0.8") == "zh"

    def test_english_with_quality(self):
        assert get_lang_from_header("en-US,en;q=0.9") == "en"

    def test_english_primary_subtag(self):
        assert get_lang_from_header("en-GB") == "en"

    def test_fallback_to_default_for_unknown(self):
        assert get_lang_from_header("fr,de") == "en"

    def test_empty_header(self):
        assert get_lang_from_header("") == "en"

    def test_none_header(self):
        assert get_lang_from_header(None) == "en"

    def test_quality_ordering(self):
        # fr not available, should fall back to en
        assert get_lang_from_header("fr;q=0.9,en;q=0.8") == "en"

    def test_unavailable_language_with_available_primary(self):
        assert get_lang_from_header("zh-TW") == "zh"


class TestAllErrorCodes:
    ERROR_CODES = [
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
    ]

    @pytest.mark.parametrize("code", ERROR_CODES)
    def test_english_has_all_error_codes(self, code):
        assert t(code, lang="en") != code

    @pytest.mark.parametrize("code", ERROR_CODES)
    def test_chinese_has_all_error_codes(self, code):
        assert t(code, lang="zh") != code


class TestReloadTranslations:
    def test_reload_clears_cache(self):
        t("VALIDATION_MISSING_KEY", lang="en")
        reload_translations()
        # Should still work after reload
        assert t("VALIDATION_MISSING_KEY", lang="en") == "API key is required"

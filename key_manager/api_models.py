from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from key_manager.errors import ErrorResponse

__all__ = [
    "ErrorResponse",
    "KeyInfo",
    "KeyListResponse",
    "KeyExportItem",
    "KeyExportResponse",
    "ImportRequest",
    "ImportResponse",
    "CheckSingleRequest",
    "CheckSingleResponse",
    "CheckBatchItem",
    "CheckBatchRequest",
    "CheckBatchResult",
    "CheckBatchSummary",
    "CheckBatchResponse",
    "TestSingleRequest",
    "TestSingleResponse",
    "BalanceRequest",
    "BalanceResponse",
    "ModelInfo",
    "ModelsResponse",
    "ProviderInfo",
    "ProvidersResponse",
    "ProviderDetail",
    "ProviderDetailResponse",
    "StatsProviderEntry",
    "StatsResponse",
    "StatsChartProviderEntry",
    "StatsChartStatuses",
    "StatsChartResponse",
    "LogEntry",
    "LogsResponse",
    "OperationEntry",
    "OperationsResponse",
    "ProgressResponse",
    "ProxyResponse",
]


# ── Keys ──────────────────────────────────────────────────────────────────────


class KeyInfo(BaseModel):
    key_masked: str = Field(..., description="Masked key for display")
    provider: str = Field(..., description="Provider identifier")
    status: str = Field(..., description="Key status: valid / invalid / error / unknown")
    last_checked: str | None = Field(None, description="ISO-8601 timestamp of last check")
    last_error: str | None = Field(None, description="Most recent error message")
    error_type: str | None = Field(None, description="Categorised error type")
    tests: dict[str, Any] = Field(default_factory=dict, description="Test results (max_tokens, max_concurrency)")
    models: list[str] = Field(default_factory=list, description="Available models")
    sources_count: int = Field(0, description="Number of import sources")
    balance: float | None = Field(None, description="Account balance if available")


class KeyListResponse(BaseModel):
    keys: list[KeyInfo] = Field(default_factory=list, description="Paginated key list")
    total: int = Field(0, description="Total number of keys matching filters")
    page: int = Field(1, description="Current page number")
    total_pages: int = Field(0, description="Total number of pages")
    page_size: int = Field(50, description="Page size")


class KeyExportItem(BaseModel):
    provider: str = Field(..., description="Provider identifier")
    max_tokens: int | None = Field(None, description="Maximum token limit")
    max_concurrency: int | None = Field(None, description="Maximum concurrency limit")


class KeyExportResponse(BaseModel):
    keys: list[KeyExportItem] = Field(default_factory=list, description="Exported valid keys")
    total: int = Field(0, description="Total exported key count")


# ── Import ────────────────────────────────────────────────────────────────────


class ImportRequest(BaseModel):
    file: str | None = Field(None, description="Path to a JSON file containing keys")
    directory: str | None = Field(None, description="Directory to scan for key files")
    batch: list[str] | None = Field(None, description="Inline list of keys to import")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"file": "./data/input/keys.json"},
                {"batch": ["sk-abc123", "sk-def456"]},
            ]
        }
    }


class ImportResponse(BaseModel):
    new: int = Field(0, description="Number of newly imported keys")
    duplicates: int = Field(0, description="Number of duplicate keys skipped")
    errors: list[str] = Field(default_factory=list, description="Import error messages")


# ── Check ─────────────────────────────────────────────────────────────────────


class CheckSingleRequest(BaseModel):
    key: str = Field(..., min_length=1, description="API key to check")
    provider: str = Field("", description="Provider name (auto-detected if empty)")
    custom_base_url: str | None = Field(None, description="Override provider base URL")

    model_config = {
        "json_schema_extra": {
            "examples": [{"key": "sk-abc123", "provider": "openai"}]
        }
    }


class CheckSingleResponse(BaseModel):
    key_masked: str = Field(..., description="Masked key for display")
    provider: str = Field(..., description="Provider identifier")
    display_name: str | None = Field(None, description="Human-readable provider name")
    status: str = Field(..., description="Check result: valid / invalid / error / unknown")
    status_code: int | None = Field(None, description="HTTP status code from provider")
    latency_ms: float = Field(0, description="Response latency in milliseconds")
    error: str | None = Field(None, description="Error message if check failed")
    error_type: str | None = Field(None, description="Categorised error type")
    balance: dict[str, Any] | None = Field(None, description="Balance information")
    models: list[str] = Field(default_factory=list, description="Available models")


class CheckBatchItem(BaseModel):
    key: str = Field(..., min_length=1, description="API key to check")
    provider: str = Field("", description="Provider name (auto-detected if empty)")


class CheckBatchRequest(BaseModel):
    keys: list[CheckBatchItem] = Field(..., min_length=1, description="Keys to check")
    timeout: int = Field(10, description="Per-key timeout in seconds")
    concurrency: int = Field(50, description="Maximum concurrent checks")
    custom_base_url: str | None = Field(None, description="Override provider base URL for all keys")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "keys": [
                        {"key": "sk-abc123", "provider": "openai"},
                        {"key": "sk-def456", "provider": "deepseek"},
                    ],
                    "concurrency": 20,
                }
            ]
        }
    }


class CheckBatchResult(BaseModel):
    key_masked: str = Field(..., description="Masked key for display")
    provider: str = Field(..., description="Provider identifier")
    status: str = Field(..., description="Check result: valid / invalid / error / unknown")
    status_code: int | None = Field(None, description="HTTP status code from provider")
    latency_ms: float = Field(0, description="Response latency in milliseconds")
    error: str | None = Field(None, description="Error message if check failed")
    error_type: str | None = Field(None, description="Categorised error type")
    balance: dict[str, Any] | None = Field(None, description="Balance information")


class CheckBatchSummary(BaseModel):
    total: int = Field(0, description="Total keys checked")
    valid: int = Field(0, description="Number of valid keys")
    invalid: int = Field(0, description="Number of invalid keys")
    error: int = Field(0, description="Number of errored keys")


class CheckBatchResponse(BaseModel):
    results: list[CheckBatchResult] = Field(default_factory=list, description="Per-key results")
    summary: CheckBatchSummary = Field(default_factory=CheckBatchSummary, description="Aggregate summary")


# ── Test ──────────────────────────────────────────────────────────────────────


class TestSingleRequest(BaseModel):
    key: str = Field(..., min_length=1, description="API key to test")
    provider: str = Field("", description="Provider name (auto-detected if empty)")

    model_config = {
        "json_schema_extra": {
            "examples": [{"key": "sk-abc123", "provider": "openai"}]
        }
    }


class TestSingleResponse(BaseModel):
    provider: str = Field(..., description="Provider identifier")
    key_masked: str = Field(..., description="Masked key for display")
    max_tokens: int | None = Field(None, description="Detected maximum token limit")
    max_concurrency: int | None = Field(None, description="Detected maximum concurrency")
    models: list[str] = Field(default_factory=list, description="Available models")
    error: str | None = Field(None, description="Error message if test failed")


# ── Balance ───────────────────────────────────────────────────────────────────


class BalanceRequest(BaseModel):
    key: str = Field(..., min_length=1, description="API key to query balance for")
    provider: str = Field("", description="Provider name (auto-detected if empty)")
    custom_base_url: str | None = Field(None, description="Override provider base URL")

    model_config = {
        "json_schema_extra": {
            "examples": [{"key": "sk-abc123", "provider": "openai"}]
        }
    }


class BalanceResponse(BaseModel):
    provider: str = Field(..., description="Provider identifier")
    supported: bool = Field(False, description="Whether provider supports balance queries")
    balance: float | None = Field(None, description="Account balance")
    currency: str | None = Field(None, description="Balance currency code")
    key_masked: str | None = Field(None, description="Masked key for display")
    error: str | None = Field(None, description="Error message if query failed")


# ── Models ────────────────────────────────────────────────────────────────────


class ModelInfo(BaseModel):
    model: str = Field(..., description="Model identifier")
    available: bool | None = Field(None, description="Whether the model is available (if checked)")


class ModelsResponse(BaseModel):
    provider: str = Field(..., description="Provider identifier")
    models: list[str] = Field(default_factory=list, description="Available model identifiers")
    total: int = Field(0, description="Total model count")
    type_filter: str = Field("all", description="Applied type filter")
    source: str | None = Field(None, description="Data source: api / static")
    hint: str | None = Field(None, description="Hint message for user")
    error: str | None = Field(None, description="Error message if fetch failed")


# ── Providers ─────────────────────────────────────────────────────────────────


class ProviderInfo(BaseModel):
    name: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Human-readable provider name")
    prefix: str = Field("-", description="Key prefix pattern")
    base_url: str = Field("", description="Provider API base URL")
    type: str = Field("ai", description="Provider type")


class ProvidersResponse(BaseModel):
    providers: list[ProviderInfo] = Field(default_factory=list, description="Registered providers")
    total: int = Field(0, description="Total provider count")


class ProviderDetail(BaseModel):
    name: str = Field(..., description="Provider identifier")
    display_name: str = Field(..., description="Human-readable provider name")
    prefix: str = Field("-", description="Key prefix pattern")
    base_url: str = Field("", description="Provider API base URL")
    website_url: str = Field("", description="Provider website URL")
    docs_url: str = Field("", description="Provider documentation URL")
    website_name: str = Field("", description="Provider website display name")


class ProviderDetailResponse(BaseModel):
    providers: list[ProviderDetail] = Field(default_factory=list, description="Provider details")
    total: int = Field(0, description="Total provider count")


# ── Stats ─────────────────────────────────────────────────────────────────────


class StatsProviderEntry(BaseModel):
    total: int = Field(0, description="Total keys for this provider")
    valid: int = Field(0, description="Valid keys")
    invalid: int = Field(0, description="Invalid keys")
    error: int = Field(0, description="Errored keys")
    display_name: str = Field("", description="Human-readable provider name")


class StatsResponse(BaseModel):
    providers: dict[str, StatsProviderEntry] = Field(
        default_factory=dict, description="Per-provider statistics"
    )
    total: int = Field(0, description="Total key count")


class StatsChartProviderEntry(BaseModel):
    total: int = Field(0, description="Total keys for this provider")
    valid: int = Field(0, description="Valid keys")
    invalid: int = Field(0, description="Invalid keys")
    error: int = Field(0, description="Errored keys")


class StatsChartStatuses(BaseModel):
    valid: int = Field(0, description="Total valid keys")
    invalid: int = Field(0, description="Total invalid keys")
    error: int = Field(0, description="Total errored keys")
    unknown: int = Field(0, description="Total unknown-status keys")


class StatsChartResponse(BaseModel):
    providers: dict[str, StatsChartProviderEntry] = Field(
        default_factory=dict, description="Per-provider breakdown for charts"
    )
    statuses: StatsChartStatuses = Field(
        default_factory=StatsChartStatuses, description="Global status counts"
    )


# ── Logs ──────────────────────────────────────────────────────────────────────


class LogEntry(BaseModel):
    timestamp: str | None = Field(None, description="Log entry timestamp")
    level: str | None = Field(None, description="Log level (INFO, WARNING, ERROR)")
    message: str = Field("", description="Log message content")
    extra: dict[str, Any] | None = Field(None, description="Additional structured data")


class LogsResponse(BaseModel):
    logs: list[LogEntry | str] = Field(default_factory=list, description="Recent log entries")
    total: int = Field(0, description="Number of entries returned")


class OperationEntry(BaseModel):
    timestamp: str | None = Field(None, description="Operation timestamp")
    action: str = Field("", description="Operation type (import, check, test, etc.)")
    detail: str = Field("", description="Operation detail")
    extra: dict[str, Any] | None = Field(None, description="Additional structured data")


class OperationsResponse(BaseModel):
    operations: list[OperationEntry | dict[str, Any]] = Field(
        default_factory=list, description="Structured operations log"
    )
    total: int = Field(0, description="Number of entries returned")


# ── Progress ──────────────────────────────────────────────────────────────────


class ProgressResponse(BaseModel):
    active: bool = Field(False, description="Whether a long-running task is in progress")
    current: int = Field(0, description="Current progress counter")
    total: int = Field(0, description="Total items to process")
    status: str = Field("", description="Task status: loading / done / error")
    results: dict[str, Any] | None = Field(None, description="Final results when complete")


# ── Proxy ─────────────────────────────────────────────────────────────────────


class ProxyResponse(BaseModel):
    proxy: str | None = Field(None, description="Detected proxy URL")
    source: str = Field("", description="Proxy source: config / env / auto / none")

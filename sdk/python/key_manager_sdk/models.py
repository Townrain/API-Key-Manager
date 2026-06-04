"""Pydantic models for API Key Manager."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class APIKey(BaseModel):
    key_masked: str
    provider: str = ""
    status: str = "unknown"
    balance: Optional[float] = None
    models: list[str] = Field(default_factory=list)
    token_limit: Optional[int] = None
    concurrency_limit: Optional[int] = None


class KeyListResponse(BaseModel):
    keys: list[APIKey] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class CheckResult(BaseModel):
    key_masked: str
    valid: bool
    provider: str = ""
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class BalanceResult(BaseModel):
    key_masked: str
    provider: str
    balance: Optional[float] = None
    currency: str = "USD"
    error: Optional[str] = None


class TestResult(BaseModel):
    key_masked: str
    provider: str
    concurrency_limit: Optional[int] = None
    token_limit: Optional[int] = None
    error: Optional[str] = None


class StatsResponse(BaseModel):
    total_keys: int = 0
    valid_keys: int = 0
    invalid_keys: int = 0
    providers: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    name: str
    display_name: str = ""
    website: Optional[str] = None
    docs: Optional[str] = None
    models: list[str] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    total: int = 0
    completed: int = 0
    running: int = 0
    failed: int = 0
    status: str = "idle"
    current_task: Optional[str] = None


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    extra: dict[str, Any] = Field(default_factory=dict)


class OperationLog(BaseModel):
    id: str
    operation: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class HTTPValidationError(BaseModel):
    detail: list[ValidationError] = Field(default_factory=list)

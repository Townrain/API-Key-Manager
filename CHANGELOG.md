# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2026-06-14

### Added

- **OpenCode Providers** — Added OpenCode Go and OpenCode Zen providers with 13 and 48 models respectively.
- **Three-Step Detection** — New detection logic: GET /v1/models to get model list, then concurrent chat/completions testing.
- **Version Path Extraction** — Extract version prefix from check_endpoint to construct correct chat URL (fixes OpenCode 404).
- **Concurrent Model Fetching** — /v1/models calls are now concurrent across all providers with 5s timeout.
- **Cherry Studio Sync** — Added ownedBy mapping for alibaba→dashscope, bytedance→doubao, xai→grok, etc.

### Changed

- **Provider Contract Tests** — Expanded from 6 to 44 providers.
- **Test Coverage** — Increased from 74% to 88% with new test files (test_proxy, test_logger, test_tester, test_core, test_api_endpoints, test_base_check).
- **Model Detection** — Removed check_model fallback for providers with /v1/models endpoint.

### Fixed

- **detect_provider Async Bug** — Fixed KeyManager.detect_provider() calling async function without await.
- **URL Construction** — Fixed chat/completions URL missing version prefix for providers like OpenCode.

## [2.1.2] - 2026-06-11

### Fixed

- **detect_provider Async** — Fixed calling async detect_provider without await and missing client parameter.

## [2.1.1] - 2026-06-11

### Fixed

- **Webhook Method Names** — Fixed all 7 webhook endpoints to use correct `WebhookManager` methods (`list_all`, `register`, `get`, `update`, `unregister`, `get_delivery_log`, `clear_delivery_log`). Previously, web.py called non-existent methods (`list_webhooks`, `add_webhook`, etc.) causing runtime crashes.
- **SSRF Validation** — Wired up `validate_custom_base_url()` to `check/single` and `balance` endpoints. Previously, the SSRF protection function existed but was never called in production code.
- **Unicode Cleanup** — Removed 32 lines of garbled unicode characters (芒聲聬, 芒聰聙) from web.py section headers and fixed garbled Chinese text in API response hints.
- **Validator Import** — Fixed wrong import path in validator.py:63 (`from src.providers.base` → `from key_manager.providers.base`).
- **StorageError Consistency** — Removed duplicate `StorageError` class from storage.py, now uses unified version from errors.py with proper `ErrorCode`.
- **Proxy Dead Code** — Removed 3 duplicate `get_proxy()` function definitions in proxy.py (lines 58-70 after return statement).
- **Auth Timing Attack** — Changed auth middleware comparison from `==` to `hmac.compare_digest()` for timing-safe authentication.

### Security

- **SSRF Protection** — `custom_base_url` parameter is now validated against provider domain whitelist before use.
- **Constant-Time Auth** — Bearer token comparison now uses `hmac.compare_digest()` to prevent timing attacks.
## [2.1.0] - 2026-06-03

### Added

- **SDK Retry Strategy** — Both sync and async SDK clients now retry on transient failures (502, 503, 504, 429, connection errors). Configurable `max_retries` parameter with exponential backoff.
- **py.typed Marker** — PEP 561 marker for type checker compatibility (mypy, pyright).
- **Rate Limiting** — Per-IP rate limiting middleware (60 requests/minute by default). Configure via `rate_limit.requests_per_minute` in config.yaml. Set to 0 to disable.
- **CI/CD Pipeline** — GitHub Actions workflow running pytest on Python 3.10, 3.11, 3.12 with ruff linting.

### Fixed

- **custom_base_url Wiring** — `custom_base_url` parameter in `CheckSingleRequest`, `CheckBatchRequest`, `TestSingleRequest`, and `BalanceRequest` is now properly applied via ContextVar. Enables using Anthropic-compatible endpoints (e.g. `https://api.deepseek.com/anthropic`).
- **TestSingleRequest** — Added missing `custom_base_url` field.
- **SDK Generator** — Retry logic is now baked into the generator so regenerations preserve retry behavior.
- **Anthropic Endpoint Auto-Detection** — When `custom_base_url` points to an Anthropic-compatible endpoint (e.g. `https://api.deepseek.com/anthropic`), the system automatically switches to Anthropic headers (`x-api-key` + `anthropic-version`), uses `/v1/models` for model listing, and uses `/v1/messages` for model probing. Affects `get_models()`, `probe()`, `test_concurrency_for_model()`, and `_probe_model()` in `ProviderBase`.
- **Smart Provider Detection** — All key check endpoints (`check/single`, `check/batch`, `test/single`, `balance`) now use `detect_provider()` instead of `detect_by_prefix()`. When a `sk-` key matches multiple providers, the system concurrently probes all candidates and uses error signature scoring to determine the correct provider, instead of blindly picking the first one.

## [2.0.0] - 2026-06-03

### Added

- **Web API Authentication** — Optional Bearer token authentication for all API endpoints. Configure via `auth.api_key` in `config.yaml` or `KEY_MANAGER_API_KEY` environment variable. Public endpoints (`/`, `/docs`, `/redoc`, `/openapi.json`) are whitelisted. Disabled by default for backward compatibility.
- **Async Python SDK** — New `AsyncKeyManagerClient` in `sdk/python/key_manager_sdk/async_client.py` using `httpx.AsyncClient`. Supports `async with` context manager. Mirrors all methods of the sync `KeyManagerClient`.
- **Changelog** — This file, following the Keep a Changelog format.

### Features (existing since 1.0.0)

- **Batch Import** — Import API keys from JSON files, directories, or direct batch input with automatic deduplication.
- **Key Validation** — Concurrent validation of keys across 45+ AI providers with configurable retry logic.
- **Capability Testing** — Token limit and concurrency testing with step-based progression.
- **Model Filtering** — Filter models by type: reasoning, vision, web, free, embedding, reranking, and tool.
- **Provider Auto-Detection** — Automatic provider detection from key prefixes (OpenAI `sk-proj-`, Anthropic `sk-ant-api03-`, Gemini `AIza`, etc.).
- **Web UI** — Cyberpunk-themed management interface built with Jinja2 templates.
- **Proxy Support** — HTTP and SOCKS5 proxy configuration for API access.
- **Model Capabilities Sync** — Daily synchronization of model capability data from Cherry Studio.
- **Encrypted Storage** — AES-256-GCM encryption for stored API keys with key rotation support.
- **API Documentation** — Auto-generated Swagger UI and Redoc documentation.
- **Internationalization** — Chinese and English error messages with Accept-Language header detection.
- **Structured Errors** — Unified `ErrorResponse` format with categorized error codes (`VALIDATION_*`, `STORAGE_*`, `PROVIDER_*`, `SYSTEM_*`, `AUTH_*`).
- **Python SDK** — Synchronous `KeyManagerClient` with typed models and exception hierarchy.
- **TypeScript SDK** — TypeScript client with full type definitions.
- **Webhook Notifications** — Event-driven webhook system with HMAC-SHA256 signature verification and delivery retries.
- **Progress Tracking** — Real-time progress updates via SSE streaming for long-running operations.
- **Balance Queries** — Check account balances for supported providers.
- **Structured Logging** — JSONL operation logs with daily rotation.

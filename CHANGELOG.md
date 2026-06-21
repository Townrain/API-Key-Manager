# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [4.0.0] - 2026-06-21

### Added

- **Frontend Modularization** — Refactored monolithic `index.html` (4725 lines) into modular structure:
  - CSS split: 5 theme files + 7 component files
    - `tokens.css` — CSS variables
    - `base.css` — Base styles, layout, responsive
    - `components.css` — Component entry (@import)
    - `components/` — 7 independent components (button, form, card, table, stat, nav, overlay)
    - `modals.css` — Modal styles
    - `animations.css` — Animations and transitions
  - JS modularization: 12 ES modules
    - `state.js` — Global state management
    - `utils.js` — Pure utility functions
    - `api/` — 9 API modules (client, stats, keys, check, test, balance, models, providers, misc)
    - UI modules: toast, progress, confirm, keys-table, providers, batch, modals, model-detect
    - `init.js` — Entry point and event binding
  - `index.html` reduced to 467 lines
- **API Module Split** — Split frontend API modules by backend route structure:
  - `api/client.js` — Shared fetch logic (safeFetch)
  - `api/index.js` — Re-exports all functions
  - Each route module has corresponding frontend file
- **Static Files Service** — Added `StaticFiles` middleware for serving CSS/JS
- **Provider System Refactoring** — Major cleanup of provider code:
  - Removed `check_model` property, providers now fetch models from API
  - Removed redundant methods from all providers (build_headers, get_models, test_token_limit, test_concurrency, _probe, check_real)
  - Standard providers reduced from ~77 lines to ~5-8 lines
  - Total reduction: ~2,400 lines of duplicated code
  - Added `chat_endpoint` property for automatic chat completions URL derivation
- **Detection Logic Fix** — Fixed provider detection to use `/chat/completions` instead of `/v1/models`:
  - `/v1/models` only returns model list, cannot determine provider
  - `/chat/completions` returns 200 only if key is valid for provider
  - Added prefix matching logic for shared prefixes (e.g., `sk-`)
  - Free models are important for detection, all models are tested
- **Documentation Update** — Added detailed detection logic documentation:
  - Updated README.md with detection flow diagram and FAQ
  - Updated docs/DEVELOPMENT.md with detection system details
  - Updated docs/PROVIDER_REFACTORING_PLAN.md with detection logic explanation
  - Added detailed comments in detector.py

### Fixed

- **Error Handling** — Added try-catch error handling to loadKeys/loadStats
- **ES Modules** — Fixed State object read-only binding issue
- **Syntax Error** — Fixed extra brace in keys-table.js goToPage function
- **SDK Documentation** — Fixed SDK method names in documentation to match actual implementation (`get_keys()` → `keys()`, etc.)
- **Encryption Key** — Fixed "No passphrase found" error by adding auto-generation of encryption key on first startup
- **Signature Report** — Fixed 404 error on signature verification report, now dynamically generates report
- **Add Provider Button** — Fixed missing "Add Provider" button in providers card, added frontend UI with modal form

### Changed

- **Web Module Refactoring** — Refactored monolithic `web.py` (2094 lines) into modular package structure:
  - `web/_app.py` — Application entry point (239 lines)
  - `web/middleware.py` — Middleware and error handlers
  - `web/progress.py` — ProgressTracker and SSE helpers
  - `web/routes/` — 8 route modules (keys, check, test, balance, models, providers, stats, misc)
- **Test Suite Refactoring** — Comprehensive cleanup and alignment of test suite:
  - Merged supplementary test files (test_parser_supplement, test_validator_supplement, test_ssrf_supplement) into main test files
  - Deleted duplicate test file (test_web_fixes) that was 100% identical to test_bug_fixes
  - Fixed mock paths to match new web module structure
  - Extracted shared fixtures and helpers to conftest.py
  - Removed 59 redundant @pytest.mark.asyncio decorators
  - Fixed rate limit middleware test isolation
- **Code Deduplication** — Eliminated duplicate model-specific check logic in `api_check_single`
- **Debug System Cleanup** — Removed `sys.path.insert` hack, using clean optional import pattern
- **Duplicate Route Fix** — Merged duplicate `GET /api/providers` routes
- **Log Display Fix** — Fixed logs displaying as `[object Object]`

### Test Coverage

- **Total Tests**: 728+ (up from 726+)
- **Coverage**: 80% (meets 60% threshold)
- **Files**: Reduced from 30 to 25 test files
### Test Coverage

- **Total Tests**: 726+ (up from 583+)
- **Coverage**: 80% (meets 60% threshold)
- **Files**: Reduced from 30 to 25 test files
## [3.2.0] - 2026-06-19

### Added

- **Per-Model Testing in Model Detection Modal** — Added ability to test Token limits and concurrency per model directly in the model detection modal.
- **Provider Management UI** — Added frontend UI for adding/managing custom providers with modal form.

### Changed

- **Removed check_model Property** — Removed `check_model` from `ProviderBase` and related fallback logic. Providers must fetch models from API.
- **Concurrency Test API** — Improved error handling with detailed error messages.

### Fixed

- **Provider Token Testing** — Fixed providers using wrong model or wrong API endpoint for token/concurrency testing.
- **Concurrency Test Client Bug** — Fixed `probe_model` using wrong httpx client.
- **Balance API** — Fixed balance checking for providers that support it.
- **Error Parsing** — Improved error message parsing for nested error objects.

## [3.1.0] - 2026-06-19

### Added

- **Provider Auto-Discovery** — Replaced 47 explicit imports with `pkgutil` auto-discovery. Providers are now auto-registered by scanning `providers/*.py`.
- **Provider Metadata Attributes** — All providers now declare `display_name`, `key_prefixes`, `error_signatures`, `website_url`, `docs_url` as class attributes.
- **Default Implementations** — `test_token_limit`, `test_concurrency`, `_probe`, `check_real` are now concrete methods in `ProviderBase`. Standard providers only need ~15 lines.
- **YAML Config Support** — Custom providers can be defined in `config.yaml` under `providers.custom` section.
- **Web API for Providers** — Added `/api/providers` CRUD endpoints for managing providers via REST API.
- **Provider Refactoring Tests** — Added `tests/test_provider_refactoring.py` with 36 tests covering auto-discovery, metadata, and backward compatibility.

### Changed

- **Code Reduction** — 39 standard providers reduced from ~100 lines to ~15 lines each (~2100 lines removed).
- **Registry Auto-Generation** — `KEY_PREFIX_MAP`, `DISPLAY_NAMES`, `PROVIDER_ERROR_SIGNATURES`, `PROVIDER_WEBSITES` are now auto-generated from provider metadata.
- **Detector Cleanup** — Removed `UNIQUE_SIGNATURES` and `KEY_PATTERNS` dicts from `detector.py`, now uses `PROVIDER_ERROR_SIGNATURES` and `KEY_PREFIX_MAP`.

### Fixed

- **NameError in test_concurrency_for_model** — Added missing `import asyncio` in `base.py:394`.
- **verify_signatures.py Import Error** — Updated to use `PROVIDER_ERROR_SIGNATURES` instead of removed `UNIQUE_SIGNATURES`.
- **DashScope Key Format** — Added `sk-ws-` prefix support for new DashScope API key format.
- **sk-sp- Mapping** — Correctly maps to `dashscope-coding` (was incorrectly mapped to `dashscope`).

## [3.0.1] - 2026-06-16

### Fixed

- **DashScope API Key Detection** — Fixed `sk-sp-` prefix mapping: now correctly maps to `dashscope-coding` (was incorrectly mapped to `dashscope`).
- **New DashScope Key Format** — Added `sk-ws-` prefix support for DashScope's new API key format.
- **Prefix Consistency** — Removed `sk-cp-` from `KEY_PATTERNS` (single-provider dict) since it maps to multiple providers (`minimax-plan` and `infini-coding`), keeping only in `KEY_PREFIX_MAP`.

## [3.0.0] - 2026-06-15

### Added

- **API Tests for 8 Endpoints** — Added tests for /api/test/token, /api/test/concurrency, /api/models/capabilities, /api/models/check, /api/progress/stream, and batch aliases.
- **Client-Side Model Caching** — Frontend caches fetched models and capabilities, type filter changes now use local filtering instead of re-fetching.
- **Full Type Filter Support** — /api/models endpoint now supports all 7 type filters (vision/tooluse/reasoning/websearch/embedding/rerank/free).

### Fixed

- **StatsChart Runtime Crash** — Fixed StatsChartProviderEntry missing provider/display_name/statuses fields, and StatsChartResponse.providers type mismatch (dict vs list).
- **KeyInfo Missing key Field** — Added key field to KeyInfo model so /api/keys returns actual key values.
- **KeyExportItem Missing key Field** — Added key field to KeyExportItem model so /api/keys/export returns actual key values.
- **Model Capabilities Extraction** — Fixed extract_model_caps.py to generate embedding_regex/rerank_regex fields and use ^$ anchoring to prevent substring false matches.
- **Cherry Studio Sync Workflow** — Fixed .github/workflows/sync-cherry-models.yml referencing stale src/providers/models_registry.py path.
- **Websearch Patterns** — Added ^$ anchoring to all capability patterns to prevent o1 matching o1-mini.
- **Autofill Styling** — Added -webkit-autofill CSS override to prevent browser autofill from turning input background white.

### Changed

- **Capability Patterns** — Changed from substring matching (re.search) to exact matching (^...$ anchored) for all model capability patterns.
- **Extraction Script** — Added rerank capability extraction from Cherry Studio's native rerank field instead of keyword splitting.

## [2.2.1] - 2026-06-14

### Fixed

- **Cherry Studio Sync** — Fixed extract_model_caps.py output path and validation test cases.

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

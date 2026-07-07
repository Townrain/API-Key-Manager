# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [4.4.0] - 2026-07-07

### Changed

- **Migrate model data source from Cherry Studio to OpenCode models.dev**
  - New script scripts/extract_from_opencode.py fetches from https://models.dev/api.json
  - Model capabilities now use explicit boolean fields (	ool_call, modalities, easoning) instead of regex matching
  - model_capabilities.py rewritten: O(1) dict lookup, 412 -> 138 lines
  - Regenerated models_registry.py: 32 providers, 1556 models (merge models.dev + preserved Cherry data)

### Removed

- is_websearch_model(), is_embedding_model(), is_rerank_model(), is_free_model() — no reliable data source in models.dev
- Frontend capability icons reduced to 3 verified types: vision, tooluse, reasoning

### Added

- .github/workflows/sync-opencode-models.yml — daily CI sync from models.dev
- data/cache/models-dev.json — local cache with 12h TTL
- Favicon for web UI

## [5.0.0] - 2026-06-26

### Added

- **Tauri Desktop App** 鈥?New native desktop client `tauri-compare` (KeyHub Desktop):
  - Cross-platform support for Windows, macOS, and Linux (Tauri v2.5)
  - Dashboard with key statistics and SSE real-time progress stream
  - Provider management with CRUD and real connection test
  - Tools panel: batch validation, model testing, signature verification report
  - Operation logs viewer and cleanup
  - Import history viewer
  - Tech stack: React 19 + TypeScript + Vite
- **Desktop CI/CD** 鈥?New GitHub Actions workflow `.github/workflows/build.yml` for PyInstaller and `cargo tauri build`
- **English README** 鈥?Added `README_EN.md` with full English documentation

### Changed


- **Model Registry Sync** 鈥?Synchronized provider models and capabilities from Cherry Studio (2026-06-27)
  - Updated `key_manager/providers/models_registry.py`
  - Added `data/model_capabilities.json`

### Fixed

- **Provider Details Endpoint** 鈥?Fixed provider detail endpoint compatibility issues
- **Real Connection Test** 鈥?Added/improved real connection testing support for provider management

## [4.3.0] - 2026-06-24

### Added

- **Coverage-Driven Testing** 鈥?Massive test coverage improvement across all web routes:
  - `detector.py`: 60% 鈫?96% 鈥?Full detection logic coverage preventing v4.2.1-class bug regressions
  - `web/routes/test.py`: 41% 鈫?99% 鈥?Test routes full coverage
  - `web/routes/providers.py`: 37% 鈫?100% 鈥?Provider CRUD full coverage
  - `web/routes/misc.py`: 53% 鈫?100% 鈥?Webhook/logs/signature report full coverage
  - `web/routes/models.py`: 72% 鈫?97% 鈥?Model endpoints full coverage
  - `web/routes/check.py`: 74% 鈫?97% 鈥?Validation endpoints full coverage
- **New Test Files**:
  - `test_detector_unit.py` (31 tests) 鈥?Detection logic unit tests covering 7 core paths
  - `test_routes_test.py` (48 tests) 鈥?Test route endpoint tests
  - `test_routes_providers.py` (32 tests) 鈥?Provider CRUD route tests
  - `test_routes_misc.py` (26 tests) 鈥?Webhook/logs/signature report route tests
  - `test_routes_models.py` (34 tests) 鈥?Model list/capabilities/SSE route tests
  - `test_routes_check.py` (23 tests) 鈥?Validation/SSRF/auto-save route tests
- **Detection Logic Regression Tests**:
  - Locks all 7 branch paths of `detect_provider()`
  - Covers both v4.2.1-fixed bugs (format match skip validation, multi-candidate early return)
  - Covers edge cases: 402 balance-insufficient detection, signature match threshold, timeout handling

### Testing

- Total: 913 tests (up from 687), coverage: 92.09% (up from 79.15%)
- 167 new tests added across 6 new test files

### Fixed

- Fixed `test_tester.py` missing `test_config` fixture parameter in `test_run_test_progress_callback`

## [4.2.1] - 2026-06-23

### Fixed

- **Detection Logic Fix** 鈥?Fixed format matching skipping validation bug: now continues concurrent probing when multiple candidates exist
- **Variable Naming** 鈥?Renamed `is_valid` to `got_models` for clearer semantics
- **Dead Code Cleanup** 鈥?Removed unreachable 500-point scoring logic from signature matching
- **Delete/Copy API Auth Fix** 鈥?Fixed `deleteKey()` and `copyKey()` using native `fetch()` causing authentication failures, changed to use `safeFetch()`

## [4.2.0] - 2026-06-23

### Added

- **Unified Authentication System** 鈥?Reuse encryption key as API authentication token:
  - New `derive_api_token()` function derives API token from encryption passphrase
  - Uses independent salt (`key-manager-api-auth-token-v1`) to avoid cross-contamination
  - PBKDF2HMAC with 600K iterations, 32-byte token, caching mechanism
  - Modified `auth_middleware()` to fallback to derived token
  - Extended auth whitelist, static files don't require authentication

- **Frontend Auto-Token Injection** 鈥?No manual configuration needed:
  - Inject `window.__API_TOKEN__` in `templates/index.html` `<head>`
  - Modified `safeFetch()` to auto-add `Authorization: Bearer <token>` header
  - Modified `models.js` SSE requests to carry token
  - Added `apiToken` field to `state.js`

- **Single Key Deletion**:
  - New `POST /api/keys/delete` API endpoint
  - Frontend delete button (trash icon) with confirmation dialog

- **Auto-Save Detected Keys**:
  - Keys are automatically saved to registry after detection
  - Updates key status and check records

- **Copy Full Key Feature**:
  - New `POST /api/keys/get-full-key` API endpoint
  - Click key in frontend to copy full key to clipboard

### Changed

- **Test Infrastructure** 鈥?Updated test fixtures to use derived token:
  - Modified `conftest.py` client fixture to derive token from passphrase
  - Added `VALIDATION_KEY_NOT_FOUND` error code
  - Updated `test_errors.py` to include new error code

### Security

- **Token Derivation** 鈥?Cryptographically secure token generation:
  - Different salt than storage encryption (domain separation)
  - PBKDF2HMAC with 600K iterations (OWASP 2023 recommendation)
  - `hmac.compare_digest()` for timing-attack resistance
  - Token cached for performance

### Testing

- Full test suite passed: 687 passed, 1 skipped
- Coverage: 75.72% (exceeds 60% requirement)
- Added 5 new `derive_api_token()` unit tests

## [4.1.0] - 2026-06-22

### Added

- **Operation Log Cleanup API** 鈥?New `DELETE /api/logs` endpoint for clearing log files:
  - Support clearing today's log (default) or specified date via query parameter
  - Returns success status, date, and number of deleted lines
  - Added `ProjectLogger.clear_main_log()` method in `logger.py`

### Changed

- **Web Module Tech Debt Cleanup** 鈥?Major code quality improvements:
  - Fixed dead code in `middleware.py` (`now - 300.0` expression result was unused)
  - Extracted `build_chat_url()` utility to `web/utils.py`, eliminating 3x duplicated URL construction
  - Extracted `resolve_provider()` utility to `web/utils.py`, eliminating 5x duplicated provider detection pattern
  - Fixed deprecated `datetime.utcnow()` in `keys.py`, replaced with `datetime.now(timezone.utc)`
  - Added `logger.debug()` to all silent exception blocks for better debugging
  - Moved inline imports (`import re as _re`, `import time as _time`) to module top-level
  - Unified error response format in `test.py` model endpoints using `ErrorResponse`
  - Removed duplicate comment in `_app.py`
  - Total code reduction: ~110 lines, new shared utility module `web/utils.py`

### Testing

- Full test suite passes: 682 passed, 1 skipped
- Coverage: 78.40% (exceeds 60% requirement)

### Frontend Cleanup

- **CSS Architecture Improvements**:
  - Added missing `--neon-cyan-dim` CSS variable to `tokens.css`
  - Created `.btn-sm`, `.btn-danger` utility classes in `button.css`
  - Created `.url-input` form class in `form.css`
  - Created `.toolbar-divider` utility class in `base.css`
  - Extracted Confirm modal inline styles to CSS classes (`.confirm-modal-content`, `.confirm-modal-body`, `.confirm-title`, `.confirm-message`, `.confirm-actions`)
  - Extracted Add Provider form inline styles to CSS classes (`.provider-form-group`, `.provider-form-label`, `.provider-form-input`, `.provider-form-actions`)
  - Extracted signature report styles to `components/signature-report.css`
  - Reduced inline `style=` attributes from 71 to 39
  - Removed all `onfocus`/`onblur` inline handlers (10 鈫?0), replaced with CSS `:focus`

- **JS Module Improvements**:
  - Extracted `selectCustomOption`, `toggleCustomSelect`, `toggleLogs` to `ui-helpers.js`
  - Added `clearLogs()` function to `api/misc.js` with confirm dialog
  - All 63 onclick handlers verified with matching `window.*` exposures
  - Zero broken import paths across 22 JS modules

- **HTML Template**:
  - `index.html` reduced from 531 to 508 lines
  - Added "Clear" button for log cleanup in the logs section

## [4.0.0] - 2026-06-21

### Added

- **Frontend Modularization** 鈥?Refactored monolithic `index.html` (4725 lines) into modular structure:
  - CSS split: 5 theme files + 7 component files
    - `tokens.css` 鈥?CSS variables
    - `base.css` 鈥?Base styles, layout, responsive
    - `components.css` 鈥?Component entry (@import)
    - `components/` 鈥?7 independent components (button, form, card, table, stat, nav, overlay)
    - `modals.css` 鈥?Modal styles
    - `animations.css` 鈥?Animations and transitions
  - JS modularization: 12 ES modules
    - `state.js` 鈥?Global state management
    - `utils.js` 鈥?Pure utility functions
    - `api/` 鈥?9 API modules (client, stats, keys, check, test, balance, models, providers, misc)
    - UI modules: toast, progress, confirm, keys-table, providers, batch, modals, model-detect
    - `init.js` 鈥?Entry point and event binding
  - `index.html` reduced to 467 lines
- **API Module Split** 鈥?Split frontend API modules by backend route structure:
  - `api/client.js` 鈥?Shared fetch logic (safeFetch)
  - `api/index.js` 鈥?Re-exports all functions
  - Each route module has corresponding frontend file
- **Static Files Service** 鈥?Added `StaticFiles` middleware for serving CSS/JS
- **Provider System Refactoring** 鈥?Major cleanup of provider code:
  - Removed `check_model` property, providers now fetch models from API
  - Removed redundant methods from all providers (build_headers, get_models, test_token_limit, test_concurrency, _probe, check_real)
  - Standard providers reduced from ~77 lines to ~5-8 lines
  - Total reduction: ~2,400 lines of duplicated code
  - Added `chat_endpoint` property for automatic chat completions URL derivation
- **Detection Logic Fix** 鈥?Fixed provider detection to use `/chat/completions` instead of `/v1/models`:
  - `/v1/models` only returns model list, cannot determine provider
  - `/chat/completions` returns 200 only if key is valid for provider
  - Added prefix matching logic for shared prefixes (e.g., `sk-`)
  - Free models are important for detection, all models are tested
- **Documentation Update** 鈥?Added detailed detection logic documentation:
  - Updated README.md with detection flow diagram and FAQ
  - Updated docs/DEVELOPMENT.md with detection system details
  - Updated docs/PROVIDER_REFACTORING_PLAN.md with detection logic explanation
  - Added detailed comments in detector.py

### Fixed

- **Error Handling** 鈥?Added try-catch error handling to loadKeys/loadStats
- **ES Modules** 鈥?Fixed State object read-only binding issue
- **Syntax Error** 鈥?Fixed extra brace in keys-table.js goToPage function
- **SDK Documentation** 鈥?Fixed SDK method names in documentation to match actual implementation (`get_keys()` 鈫?`keys()`, etc.)
- **Encryption Key** 鈥?Fixed "No passphrase found" error by adding auto-generation of encryption key on first startup
- **Signature Report** 鈥?Fixed 404 error on signature verification report, now dynamically generates report
- **Add Provider Button** 鈥?Fixed missing "Add Provider" button in providers card, added frontend UI with modal form

### Changed

- **Web Module Refactoring** 鈥?Refactored monolithic `web.py` (2094 lines) into modular package structure:
  - `web/_app.py` 鈥?Application entry point (239 lines)
  - `web/middleware.py` 鈥?Middleware and error handlers
  - `web/progress.py` 鈥?ProgressTracker and SSE helpers
  - `web/routes/` 鈥?8 route modules (keys, check, test, balance, models, providers, stats, misc)
- **Test Suite Refactoring** 鈥?Comprehensive cleanup and alignment of test suite:
  - Merged supplementary test files (test_parser_supplement, test_validator_supplement, test_ssrf_supplement) into main test files
  - Deleted duplicate test file (test_web_fixes) that was 100% identical to test_bug_fixes
  - Fixed mock paths to match new web module structure
  - Extracted shared fixtures and helpers to conftest.py
  - Removed 59 redundant @pytest.mark.asyncio decorators
  - Fixed rate limit middleware test isolation
- **Code Deduplication** 鈥?Eliminated duplicate model-specific check logic in `api_check_single`
- **Debug System Cleanup** 鈥?Removed `sys.path.insert` hack, using clean optional import pattern
- **Duplicate Route Fix** 鈥?Merged duplicate `GET /api/providers` routes
- **Log Display Fix** 鈥?Fixed logs displaying as `[object Object]`

### Test Coverage

- **Total Tests**: 728+ (up from 726+)
- **Coverage**: 80% (meets 60% threshold)
- **Files**: Reduced from 30 to 25 test files
## [3.2.0] - 2026-06-19

### Added

- **Per-Model Testing in Model Detection Modal** 鈥?Added ability to test Token limits and concurrency per model directly in the model detection modal.
- **Provider Management UI** 鈥?Added frontend UI for adding/managing custom providers with modal form.

### Changed

- **Removed check_model Property** 鈥?Removed `check_model` from `ProviderBase` and related fallback logic. Providers must fetch models from API.
- **Concurrency Test API** 鈥?Improved error handling with detailed error messages.

### Fixed

- **Provider Token Testing** 鈥?Fixed providers using wrong model or wrong API endpoint for token/concurrency testing.
- **Concurrency Test Client Bug** 鈥?Fixed `probe_model` using wrong httpx client.
- **Balance API** 鈥?Fixed balance checking for providers that support it.
- **Error Parsing** 鈥?Improved error message parsing for nested error objects.

## [3.1.0] - 2026-06-19

### Added

- **Provider Auto-Discovery** 鈥?Replaced 47 explicit imports with `pkgutil` auto-discovery. Providers are now auto-registered by scanning `providers/*.py`.
- **Provider Metadata Attributes** 鈥?All providers now declare `display_name`, `key_prefixes`, `error_signatures`, `website_url`, `docs_url` as class attributes.
- **Default Implementations** 鈥?`test_token_limit`, `test_concurrency`, `_probe`, `check_real` are now concrete methods in `ProviderBase`. Standard providers only need ~15 lines.
- **YAML Config Support** 鈥?Custom providers can be defined in `config.yaml` under `providers.custom` section.
- **Web API for Providers** 鈥?Added `/api/providers` CRUD endpoints for managing providers via REST API.
- **Provider Refactoring Tests** 鈥?Added `tests/test_provider_refactoring.py` with 36 tests covering auto-discovery, metadata, and backward compatibility.

### Changed

- **Code Reduction** 鈥?39 standard providers reduced from ~100 lines to ~15 lines each (~2100 lines removed).
- **Registry Auto-Generation** 鈥?`KEY_PREFIX_MAP`, `DISPLAY_NAMES`, `PROVIDER_ERROR_SIGNATURES`, `PROVIDER_WEBSITES` are now auto-generated from provider metadata.
- **Detector Cleanup** 鈥?Removed `UNIQUE_SIGNATURES` and `KEY_PATTERNS` dicts from `detector.py`, now uses `PROVIDER_ERROR_SIGNATURES` and `KEY_PREFIX_MAP`.

### Fixed

- **NameError in test_concurrency_for_model** 鈥?Added missing `import asyncio` in `base.py:394`.
- **verify_signatures.py Import Error** 鈥?Updated to use `PROVIDER_ERROR_SIGNATURES` instead of removed `UNIQUE_SIGNATURES`.
- **DashScope Key Format** 鈥?Added `sk-ws-` prefix support for new DashScope API key format.
- **sk-sp- Mapping** 鈥?Correctly maps to `dashscope-coding` (was incorrectly mapped to `dashscope`).

## [3.0.1] - 2026-06-16

### Fixed

- **DashScope API Key Detection** 鈥?Fixed `sk-sp-` prefix mapping: now correctly maps to `dashscope-coding` (was incorrectly mapped to `dashscope`).
- **New DashScope Key Format** 鈥?Added `sk-ws-` prefix support for DashScope's new API key format.
- **Prefix Consistency** 鈥?Removed `sk-cp-` from `KEY_PATTERNS` (single-provider dict) since it maps to multiple providers (`minimax-plan` and `infini-coding`), keeping only in `KEY_PREFIX_MAP`.

## [3.0.0] - 2026-06-15

### Added

- **API Tests for 8 Endpoints** 鈥?Added tests for /api/test/token, /api/test/concurrency, /api/models/capabilities, /api/models/check, /api/progress/stream, and batch aliases.
- **Client-Side Model Caching** 鈥?Frontend caches fetched models and capabilities, type filter changes now use local filtering instead of re-fetching.
- **Full Type Filter Support** 鈥?/api/models endpoint now supports all 7 type filters (vision/tooluse/reasoning/websearch/embedding/rerank/free).

### Fixed

- **StatsChart Runtime Crash** 鈥?Fixed StatsChartProviderEntry missing provider/display_name/statuses fields, and StatsChartResponse.providers type mismatch (dict vs list).
- **KeyInfo Missing key Field** 鈥?Added key field to KeyInfo model so /api/keys returns actual key values.
- **KeyExportItem Missing key Field** 鈥?Added key field to KeyExportItem model so /api/keys/export returns actual key values.
- **Model Capabilities Extraction** 鈥?Fixed extract_model_caps.py to generate embedding_regex/rerank_regex fields and use ^$ anchoring to prevent substring false matches.
- **Cherry Studio Sync Workflow** 鈥?Fixed .github/workflows/sync-cherry-models.yml referencing stale src/providers/models_registry.py path.
- **Websearch Patterns** 鈥?Added ^$ anchoring to all capability patterns to prevent o1 matching o1-mini.
- **Autofill Styling** 鈥?Added -webkit-autofill CSS override to prevent browser autofill from turning input background white.

### Changed

- **Capability Patterns** 鈥?Changed from substring matching (re.search) to exact matching (^...$ anchored) for all model capability patterns.
- **Extraction Script** 鈥?Added rerank capability extraction from Cherry Studio's native rerank field instead of keyword splitting.

## [2.2.1] - 2026-06-14

### Fixed

- **Cherry Studio Sync** 鈥?Fixed extract_model_caps.py output path and validation test cases.

## [2.2.0] - 2026-06-14

### Added

- **OpenCode Providers** 鈥?Added OpenCode Go and OpenCode Zen providers with 13 and 48 models respectively.
- **Three-Step Detection** 鈥?New detection logic: GET /v1/models to get model list, then concurrent chat/completions testing.
- **Version Path Extraction** 鈥?Extract version prefix from check_endpoint to construct correct chat URL (fixes OpenCode 404).
- **Concurrent Model Fetching** 鈥?/v1/models calls are now concurrent across all providers with 5s timeout.
- **Cherry Studio Sync** 鈥?Added ownedBy mapping for alibaba鈫抎ashscope, bytedance鈫抎oubao, xai鈫抔rok, etc.

### Changed

- **Provider Contract Tests** 鈥?Expanded from 6 to 44 providers.
- **Test Coverage** 鈥?Increased from 74% to 88% with new test files (test_proxy, test_logger, test_tester, test_core, test_api_endpoints, test_base_check).
- **Model Detection** 鈥?Removed check_model fallback for providers with /v1/models endpoint.

### Fixed

- **detect_provider Async Bug** 鈥?Fixed KeyManager.detect_provider() calling async function without await.
- **URL Construction** 鈥?Fixed chat/completions URL missing version prefix for providers like OpenCode.

## [2.1.2] - 2026-06-11

### Fixed

- **detect_provider Async** 鈥?Fixed calling async detect_provider without await and missing client parameter.

## [2.1.1] - 2026-06-11

### Fixed

- **Webhook Method Names** 鈥?Fixed all 7 webhook endpoints to use correct `WebhookManager` methods (`list_all`, `register`, `get`, `update`, `unregister`, `get_delivery_log`, `clear_delivery_log`). Previously, web.py called non-existent methods (`list_webhooks`, `add_webhook`, etc.) causing runtime crashes.
- **SSRF Validation** 鈥?Wired up `validate_custom_base_url()` to `check/single` and `balance` endpoints. Previously, the SSRF protection function existed but was never called in production code.
- **Unicode Cleanup** 鈥?Removed 32 lines of garbled unicode characters (鑺掕伈鑱? 鑺掕伆鑱? from web.py section headers and fixed garbled Chinese text in API response hints.
- **Validator Import** 鈥?Fixed wrong import path in validator.py:63 (`from src.providers.base` 鈫?`from key_manager.providers.base`).
- **StorageError Consistency** 鈥?Removed duplicate `StorageError` class from storage.py, now uses unified version from errors.py with proper `ErrorCode`.
- **Proxy Dead Code** 鈥?Removed 3 duplicate `get_proxy()` function definitions in proxy.py (lines 58-70 after return statement).
- **Auth Timing Attack** 鈥?Changed auth middleware comparison from `==` to `hmac.compare_digest()` for timing-safe authentication.

### Security

- **SSRF Protection** 鈥?`custom_base_url` parameter is now validated against provider domain whitelist before use.
- **Constant-Time Auth** 鈥?Bearer token comparison now uses `hmac.compare_digest()` to prevent timing attacks.
## [2.1.0] - 2026-06-03

### Added

- **SDK Retry Strategy** 鈥?Both sync and async SDK clients now retry on transient failures (502, 503, 504, 429, connection errors). Configurable `max_retries` parameter with exponential backoff.
- **py.typed Marker** 鈥?PEP 561 marker for type checker compatibility (mypy, pyright).
- **Rate Limiting** 鈥?Per-IP rate limiting middleware (60 requests/minute by default). Configure via `rate_limit.requests_per_minute` in config.yaml. Set to 0 to disable.
- **CI/CD Pipeline** 鈥?GitHub Actions workflow running pytest on Python 3.10, 3.11, 3.12 with ruff linting.

### Fixed

- **custom_base_url Wiring** 鈥?`custom_base_url` parameter in `CheckSingleRequest`, `CheckBatchRequest`, `TestSingleRequest`, and `BalanceRequest` is now properly applied via ContextVar. Enables using Anthropic-compatible endpoints (e.g. `https://api.deepseek.com/anthropic`).
- **TestSingleRequest** 鈥?Added missing `custom_base_url` field.
- **SDK Generator** 鈥?Retry logic is now baked into the generator so regenerations preserve retry behavior.
- **Anthropic Endpoint Auto-Detection** 鈥?When `custom_base_url` points to an Anthropic-compatible endpoint (e.g. `https://api.deepseek.com/anthropic`), the system automatically switches to Anthropic headers (`x-api-key` + `anthropic-version`), uses `/v1/models` for model listing, and uses `/v1/messages` for model probing. Affects `get_models()`, `probe()`, `test_concurrency_for_model()`, and `_probe_model()` in `ProviderBase`.
- **Smart Provider Detection** 鈥?All key check endpoints (`check/single`, `check/batch`, `test/single`, `balance`) now use `detect_provider()` instead of `detect_by_prefix()`. When a `sk-` key matches multiple providers, the system concurrently probes all candidates and uses error signature scoring to determine the correct provider, instead of blindly picking the first one.

## [2.0.0] - 2026-06-03

### Added

- **Web API Authentication** 鈥?Optional Bearer token authentication for all API endpoints. Configure via `auth.api_key` in `config.yaml` or `KEY_MANAGER_API_KEY` environment variable. Public endpoints (`/`, `/docs`, `/redoc`, `/openapi.json`) are whitelisted. Disabled by default for backward compatibility.
- **Async Python SDK** 鈥?New `AsyncKeyManagerClient` in `sdk/python/key_manager_sdk/async_client.py` using `httpx.AsyncClient`. Supports `async with` context manager. Mirrors all methods of the sync `KeyManagerClient`.
- **Changelog** 鈥?This file, following the Keep a Changelog format.

### Features (existing since 1.0.0)

- **Batch Import** 鈥?Import API keys from JSON files, directories, or direct batch input with automatic deduplication.
- **Key Validation** 鈥?Concurrent validation of keys across 45+ AI providers with configurable retry logic.
- **Capability Testing** 鈥?Token limit and concurrency testing with step-based progression.
- **Model Filtering** 鈥?Filter models by type: reasoning, vision, web, free, embedding, reranking, and tool.
- **Provider Auto-Detection** 鈥?Automatic provider detection from key prefixes (OpenAI `sk-proj-`, Anthropic `sk-ant-api03-`, Gemini `AIza`, etc.).
- **Web UI** 鈥?Cyberpunk-themed management interface built with Jinja2 templates.
- **Proxy Support** 鈥?HTTP and SOCKS5 proxy configuration for API access.
- **Model Capabilities Sync** 鈥?Daily synchronization of model capability data from Cherry Studio.
- **Encrypted Storage** 鈥?AES-256-GCM encryption for stored API keys with key rotation support.
- **API Documentation** 鈥?Auto-generated Swagger UI and Redoc documentation.
- **Internationalization** 鈥?Chinese and English error messages with Accept-Language header detection.
- **Structured Errors** 鈥?Unified `ErrorResponse` format with categorized error codes (`VALIDATION_*`, `STORAGE_*`, `PROVIDER_*`, `SYSTEM_*`, `AUTH_*`).
- **Python SDK** 鈥?Synchronous `KeyManagerClient` with typed models and exception hierarchy.
- **TypeScript SDK** 鈥?TypeScript client with full type definitions.
- **Webhook Notifications** 鈥?Event-driven webhook system with HMAC-SHA256 signature verification and delivery retries.
- **Progress Tracking** 鈥?Real-time progress updates via SSE streaming for long-running operations.
- **Balance Queries** 鈥?Check account balances for supported providers.
- **Structured Logging** 鈥?JSONL operation logs with daily rotation.

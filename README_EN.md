[![PyPI version](https://img.shields.io/pypi/v/api-key-manager)](https://pypi.org/project/api-key-manager/)

[中文](README.md) | English

# API Key Manager

Python tool for batch managing API keys for 45+ AI providers, with CLI, Web, and Desktop interfaces.

## Features

- **Batch Import** - Import API keys from JSON files, automatic deduplication
- **Key Validation** - Concurrent key validity checking, supports 45+ AI providers
- **Capability Testing** - Test token limits and concurrency capabilities
- **Model Filtering** - Filter models by type (reasoning/vision/web search/free/embedding/rerank/tools)
- **Smart Detection** - Prefix matching + pattern matching + error signature matching, three-level provider auto-detection
- **Auto-Discovery** - New providers are automatically registered by just creating a Python file
- **Extensible Architecture** - YAML configuration for custom providers, Web API management
- **Web Interface** - Cyberpunk-style management dashboard
- **Proxy Support** - HTTP/SOCKS proxy support
- **Encrypted Storage** - AES-256-GCM encrypted storage for API keys with random salt
- **Security Protection** - Path traversal protection, SSRF protection, timing-safe authentication
- **API Documentation** - Swagger UI and Redoc auto-generated docs
- **Internationalization** - Chinese and English error messages
- **SDK Support** - Python and TypeScript client libraries
- **Desktop App** - Single-file portable exe with pywebview window
- **Webhook Notifications** - Event-driven webhook notification system

## System Architecture

![系统架构流程图](docs/images/flowchart.png)


## Supported AI Providers

### International

| Provider | Prefix |
|----------|--------|
| OpenAI | `sk-proj-` |
| Anthropic | `sk-ant-api03-` |
| Google Gemini | `AIza` |
| DeepSeek | `sk-` |
| Groq | `gsk_` |
| Mistral | `sk-` |
| Cohere | `sk-` |
| Perplexity | `pplx-` |
| Together AI | `sk-` |
| Replicate | `r8_` |
| Hugging Face | `hf_` |
| Fireworks | `fw_` |
| OpenRouter | `sk-or-v1-` |
| Grok (xAI) | `xai-` |
| Cerebras | `sk-` |
| NVIDIA | `sk-` |
| Hyperbolic | `sk-` |
| Poe | `sk-` |

### China

| Provider | Prefix | Display Name |
|----------|--------|--------------|
| 阿里百炼 | `sk-ws-` / `sk-` |
| 阿里百炼编程 | `sk-sp-` |
| ModelScope | `ms-` | ModelScope (魔搭) |
| Zhipu GLM | `sk-` | Zhipu (智谱) |
| Kimi | `sk-` | Kimi (月之暗面) |
| MiniMax | `sk-` | MiniMax |
| SiliconFlow | `sk-` | SiliconFlow (硅基流动) |
| Baichuan | `sk-` | Baichuan (百川) |
| Yi | `sk-` | Yi (零一万物) |
| StepFun | `sk-` | StepFun (阶跃星辰) |
| Doubao | `sk-` | Doubao (豆包) |
| Infini | `sk-` | Infini (无问芯穹) |
| MiMo | `sk-` | MiMo (小米) |
| Tencent Hunyuan | `sk-` | Tencent Hunyuan (腾讯混元) |
| CSTCloud | `sk-` | CSTCloud (中算云) |

### New Providers

| Provider | Description |
|----------|-------------|
| LongCat | New |
| AI302 | New |
| PPIO | New |
| DMXAPI | New |
| OCoolAI | New |
| ZAI | New |
| MiMo Plan | Plan version |
| MiniMax Plan | Plan version |
| DashScope Coding | Coding version |
| Zhipu Coding | Coding version |
| Kimi Coding | Coding version |
| Infini Coding | Coding version |

## Adding Custom Providers

### Method 1: Python File (Recommended)

Create `key_manager/providers/my_llm.py`:

```python
from .base import ProviderBase


class MyLlmProvider(ProviderBase):
    name = "my-llm"
    base_url = "https://api.my-llm.com/v1"
    check_endpoint = "/models"
    check_model = "my-model"
    display_name = "My LLM"
    key_prefixes = ["myllm-"]
    error_signatures = ["my-llm", "invalid api key"]
    website_url = "https://my-llm.com"
    docs_url = "https://docs.my-llm.com"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}
```

Restart the service to auto-discover the new provider.

### Method 2: YAML Configuration

Add to `config.yaml`:

```yaml
providers:
  custom:
    - name: "my-llm"
      base_url: "https://api.my-llm.com/v1"
      check_endpoint: "/models"
      check_model: "my-model"
      display_name: "My LLM"
      key_prefixes: ["myllm-"]
      auth_type: bearer
```

### Method 3: Web API

```bash
# Add a provider
curl -X POST http://localhost:18001/api/providers \
  -H "Content-Type: application/json" \
  -d '{"name":"my-llm","base_url":"https://api.my-llm.com/v1","check_endpoint":"/models"}'

# List all providers
curl http://localhost:18001/api/providers

# Delete a provider
curl -X DELETE http://localhost:18001/api/providers/my-llm
```

## Quick Start

### Desktop App (v5.0.0)

Download `KeyHub-Setup.exe` from [Releases](https://github.com/Townrain/API-Key-Manager/releases) and install to any directory.

### Installation

```bash
# Install from PyPI (recommended)
pip install api-key-manager
```

```bash
# Or install from source (development mode)
git clone https://github.com/Townrain/API-Key-Manager.git
cd key

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (includes testing tools)
pip install -e ".[dev]"
```

### CLI Usage

```bash
# Import keys
python main.py import --file data/input/example.json
python main.py import --dir ./data/input

# Validate keys
python main.py check
python main.py check --provider openai
python main.py check --key sk-xxx

# Test keys
python main.py test
python main.py test --skip-token
python main.py test --skip-concurrency

# List keys
python main.py list --provider anthropic --status valid
python main.py list --status invalid

# Generate report
python main.py report --days 7
```

### Web Interface

```bash
# Start the web server
python web.py

# Access the following URLs:
# Main interface: http://localhost:18001
# API docs: http://localhost:18001/docs
# Redoc: http://localhost:18001/redoc
```

## Security Features

### Encrypted Storage

API keys support AES-256-GCM encrypted storage (enabled by default), with a random salt for each encryption:

```bash
# Set encryption key (environment variable)
set KEY_MANAGER_SECRET=your-secret-key

# Start the service
python web.py
```

Encrypted `keys.json` format:
```json
{
  "encrypted": true,
  "salt": "base64-encoded-random-salt",
  "nonce": "base64-encoded-nonce",
  "data": "base64-encoded-ciphertext"
}
```

#### Optional Encryption Toggle

Starting from v4.2.0, encryption can be disabled via configuration to store keys in plaintext (useful for local development):

```yaml
# config.yaml
storage:
  keys_file: "./data/keys.json"
  encrypted: false  # Plaintext storage (recommended for local development)
  # encrypted: true  # Encrypted storage (recommended for production, default)
```

**Notes:**
- `encrypted: true` (default) - Uses AES-256-GCM encryption, requires `KEY_MANAGER_SECRET` to be set
- `encrypted: false` - Plaintext JSON storage, no encryption key needed, easy for debugging and migration
- `load()` auto-detects file format, can read existing files regardless of configuration

### Security Protection

- **Path Traversal Protection** - Import endpoint validates paths are within allowed directories
- **SSRF Protection** - `custom_base_url` validates domain whitelist, blocks private IPs, integrated with `check/single` and `balance` endpoints
- **Timing-Safe Authentication** - Uses `hmac.compare_digest()` to prevent timing attacks
- **Auth Warning** - Startup warning when API Key is not configured
- **Key Masking** - API responses only return `key_masked`, full keys are never exposed
- **Webhook Security** - Webhook endpoints use correct API methods, preventing runtime errors

### API Authentication

```bash
# Set API Key (environment variable)
set KEY_MANAGER_API_KEY=your-api-key

# Or configure in config.yaml
# auth:
#   api_key: "your-api-key"
```

## Provider Smart Detection

### Detection Strategy

The system uses a **full concurrent probing** strategy to automatically identify API keys from 45+ AI providers.

### Detection Flow (Important!)

```
1. Prefix Matching - Check unique prefixes (e.g., sk-proj- → OpenAI, AIza → Google)
2. Format Matching - Check special formats (e.g., Zhipu's {id}.{secret} format)
3. Full Concurrent Probing - Simultaneously send requests to all providers
4. Signature Matching - If no 200 response, identify provider through error response body signatures
```

### ⚠️ Key Concept: /v1/models vs /chat/completions

**These two endpoints have completely different purposes and cannot be used interchangeably!**

| Endpoint | Purpose | Meaning of 200 Response |
|----------|---------|------------------------|
| `/v1/models` | Get model list | Only means the model list can be retrieved, **cannot** determine if the key is valid |
| `/chat/completions` | Call a model | Means the key is valid for that provider, **this is the basis for determining the provider** |

**Common Mistakes:**
- ❌ Using `/v1/models` returning 200 to determine the provider → Wrong!
- ✅ Using `/chat/completions` returning 200 to determine the provider → Correct!

### Detection Flow Details

#### Step 1: Prefix Matching

Check if the key matches a unique prefix:

```python
# Unique prefix → return directly
"sk-proj-" → OpenAI
"sk-ant-api03-" → Anthropic
"AIza" → Google
"ms-" → ModelScope

# Shared prefix → needs further probing
"sk-" → 20+ providers (DeepSeek, OpenAI, etc.)
```

#### Step 2: Format Matching

Check if the key matches a special format:

```python
# Zhipu/Z.AI format: {id}.{secret}
50bcde33b8774aa8a2cc1bd6d39444ae.ifriyNWRLStzpLEs
→ Returns ["zhipu", "zai"]
```

#### Step 3: Full Concurrent Probing (Core Logic)

**Important: This step uses `/chat/completions` for verification, not `/v1/models`!**

```python
async def detect_provider(client, key):
    # Step 3.1: Get model lists from all providers (/v1/models)
    # This step only retrieves model lists, cannot determine provider
    models = {}
    for name, provider in PROVIDERS.items():
        resp = await client.get(f"{provider.base_url}/v1/models")
        if resp.status_code == 200:
            models[name] = extract_models(resp.json())
    
    # Step 3.2: Concurrently test all (provider, model) pairs with /chat/completions
    # This step is the basis for determining the provider!
    tasks = []
    for name, model_list in models.items():
        for model in model_list:
            tasks.append(try_chat_completion(name, model))
    
    # First provider returning 200 wins
    for coro in asyncio.as_completed(tasks):
        name, valid, status_code = await coro
        if valid:  # /chat/completions returns 200
            return name
```

#### Step 4: Signature Matching

If all `/chat/completions` fail, identify the provider through error response bodies:

```python
# Error signature matching
UNIQUE_SIGNATURES = {
    "dashscope": ["model-studio", "modelstudio", "apikey-error"],
    "anthropic": ["request not allowed", "anthropic", "x-api-key"],
    "openai": ["platform.openai.com"],
    # ... more signatures
}

# Matching threshold: at least 2 signature matches (200 points) to return result
if best_score >= 200:
    return best_name
```

### Importance of Free Models

**Some providers (like OpenCode Zen) offer free models, which are very important for detection!**

```python
# OpenCode Zen's model list:
# - claude-fable-5 (paid)
# - deepseek-v4-flash-free (free) ✅
# - mimo-v2.5-free (free) ✅
# - ...

# If the key only has access to free models:
# - /chat/completions + claude-fable-5 → 401 (paid model, no permission)
# - /chat/completions + deepseek-v4-flash-free → 200 (free model, has permission) ✅
```

**The detection logic concurrently tests all models, including free models. As long as one model returns 200, the provider will be correctly identified.**

### Detection Priority

| Priority | Method | Endpoint | Description |
|----------|--------|----------|-------------|
| 1 | Prefix Matching | - | Unique prefix, e.g., `sk-proj-` → OpenAI |
| 2 | Format Matching | - | Special format, e.g., `{id}.{secret}` → Zhipu |
| 3 | Full Concurrent Probing | `/chat/completions` | First provider returning 200 wins |
| 4 | Signature Matching | - | Identify through error response bodies, requires at least 2 signature matches |

### FAQ

#### Q: Why is my key incorrectly identified as another provider?

**A: This could be because:**
1. The key uses a shared prefix (like `sk-`), needs verification via `/chat/completions`
2. The key only has access to free models, but the detection logic didn't test free models
3. The provider's `/v1/models` returns 200, but `/chat/completions` returns 401

#### Q: Why does `/v1/models` return 200 but detection fails?

**A: Because `/v1/models` returning 200 cannot determine the provider!**
- `/v1/models` only means the model list can be retrieved
- `/chat/completions` returning 200 is needed to determine the provider

#### Q: How to ensure correct detection?

**A: Make sure of the following:**
1. The key has permission to call at least one model (including free models)
2. The provider's `/chat/completions` endpoint is working properly
3. The key has not expired or been revoked

### Detection Flow Chart

```
Input: API Key
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: Prefix Matching                                     │
│   - Unique prefix → return directly (e.g., sk-proj- → OpenAI) │
│   - Shared prefix → continue to next step                   │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: Format Matching                                     │
│   - Zhipu format {id}.{secret} → return ["zhipu", "zai"]   │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: Full Concurrent Probing (verify with /chat/completions) │
│                                                             │
│   3.1 Get model lists from all providers (/v1/models)       │
│       - This step only retrieves models, cannot determine provider │
│                                                             │
│   3.2 Concurrently test all (provider, model) pairs         │
│       with /chat/completions                                │
│       - First provider returning 200 wins                   │
│       - Includes both free and paid models                  │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: Signature Matching (if all /chat/completions fail)  │
│   - Identify provider through keywords in error response body │
│   - Requires at least 2 signature matches (200 points) to return result │
└─────────────────────────────────────────────────────────────┘
```

### Code Implementation

The detection logic is implemented in `key_manager/detector.py`:

```python
async def detect_provider(client, key: str, suspected_provider: str = None) -> str:
    """Detect provider by concurrently probing ALL providers with multiple models.
    
    Strategy:
    1. If suspected_provider given, try it first
    2. If key matches unique pattern, try that provider
    3. Otherwise, concurrently probe ALL providers with their top 5 models
    4. First provider returning 200 wins
    """
    # Step 1: If suspected provider, try it first
    if suspected_provider:
        provider_name = suspected_provider.lower()
        if provider_name in PROVIDERS:
            return provider_name
    
    # Step 2: Try format matching (e.g., Zhipu's {id}.{secret})
    format_candidates = detect_by_format(key)
    if format_candidates:
        for name in format_candidates:
            if name in PROVIDERS:
                return name
    
    # Step 3: Try prefix matching
    prefix_candidates = detect_by_prefix(key)
    if prefix_candidates:
        if len(prefix_candidates) == 1:
            return prefix_candidates[0]
        # If multiple candidates, continue to Step 4
    
    # Step 4: Concurrently probe ALL providers
    # First, get models from all providers concurrently
    model_tasks = [get_provider_models(name, provider) for name, provider in PROVIDERS.items()]
    model_results = await asyncio.gather(*model_tasks)
    
    # Build tasks: (provider_name, model) pairs
    tasks = []
    for name, models, is_valid in model_results:
        if models:
            for model in models:
                tasks.append((name, model))
    
    # Concurrently check all (provider, model) pairs
    all_tasks = [try_model(name, model) for name, model in tasks]
    
    # First provider returning 200 wins
    for coro in asyncio.as_completed(all_tasks):
        name, valid, body, status_code = await coro
        if valid:
            return name
    
    # Step 5: Signature matching
    return match_by_signature(error_bodies)
```

## Error Message Simplification

The system automatically simplifies raw error messages from providers into user-friendly prompts:

| Raw Error Message | Simplified |
|-------------------|------------|
| `Access denied, please make sure your account is in good standing...` | Insufficient balance |
| `Invalid API Key` | Invalid key |
| `Authentication fails` | Authentication failed |
| `Token expired` | Key expired |
| `Rate limit exceeded` | Rate limit exceeded |
| `Account suspended` | Account suspended |
| `Access denied` | Access denied |
| `Model does not exist` | Model not found |

Error message simplification is implemented in the `simplify_error()` function in `base.py`, supporting:

- Status code-based simplification (401 → Invalid key, 402 → Insufficient balance, 429 → Rate limit exceeded)
- Keyword-based pattern matching (authentication, expired, rate limit, etc.)
- Long error message truncation (truncate and add ellipsis when exceeding 100 characters)

## Model Detection

### Model List Source

The system syncs model data from OpenCode [models.dev](https://models.dev), generating a `models_registry.py` file (Chinese providers retain Cherry Studio data):

```python
PROVIDER_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", ...],
    "anthropic": ["claude-3-opus", "claude-3-sonnet", ...],
    "dashscope": ["qwen-turbo", "qwen-plus", "qwen-max", ...],
    "siliconflow": ["Qwen/Qwen2.5-7B-Instruct", ...],
    # ... 45+ providers
}
```

### Model Detection Flow

When the user clicks "Detect Available Models":

1. Get the provider's model list (prefer API response, fall back to static list)
2. Concurrently detect each model's availability (batch_size dynamically adjusted)
3. Send a minimal request for each model (`POST /chat/completions`, `max_tokens: 5`)
4. Models returning 200 are marked as available, others marked as failed
5. Failed models are retried serially (up to 2 times)

```python
# Model detection logic
async def check_model(http, model):
    resp = await client.post(
        f"{provider.get_base_url()}/chat/completions",
        json={"model": model, "messages": [...], "max_tokens": 5}
    )
    return model, 200 if resp.status_code == 200 else resp.status_code

# Dynamic concurrency control
batch_size = 5  # Initial concurrency
for i in range(0, len(models), batch_size):
    batch = models[i:i+batch_size]
    results = await asyncio.gather(*[check_model(http, m) for m in batch])
    
    # All success → concurrency +1
    if all_success:
        batch_size += 1
    # Has failures → keep current concurrency
    
    # Serial retry for failed models
    for model in failed_models:
        _, code = await check_model(http, model)
        if code == 200:
            # Retry succeeded
```

### Model Capability Detection

The system supports filtering models by type:

| Type | Description | Filter Method | Source |
|------|-------------|---------------|--------|
| Vision Models | Support image input | `is_vision_model()` | models.dev |
| Tool Models | Support function calling | `is_tool_model()` | models.dev |
| Reasoning Models | Support chain of thought | `is_reasoning_model()` | models.dev |

Capability data (vision / tooluse / reasoning) is synced from [models.dev](https://models.dev/api.json) using explicit boolean fields, stored in `data/model_capabilities.json`.

### Model Capability Note

> **v4.4**: Capability detection migrated from Cherry Studio regex to [OpenCode models.dev](https://models.dev) explicit fields.
> Only three reliable capabilities: **vision** (`modalities.input`), **tooluse** (`tool_call`), **reasoning** (`reasoning`).
> New script `scripts/extract_from_opencode.py`, CI `.github/workflows/sync-opencode-models.yml` daily sync.

## Project Structure
```
key/
├── key_manager/                    # Core package
│   ├── __init__.py                 # Package exports
│   ├── cli.py                      # CLI entry point
│   ├── web/                        # Web module (v4.0.0 refactor)
│   │   ├── __init__.py             # Package exports
│   │   ├── _app.py                 # FastAPI application entry
│   │   ├── middleware.py           # Middleware and error handlers
│   │   ├── progress.py             # ProgressTracker and SSE helpers
│   │   └── routes/                 # Route modules
│   │       ├── keys.py             # Key management routes
│   │       ├── check.py            # Validation routes
│   │       ├── test.py             # Testing routes
│   │       ├── balance.py          # Balance query routes
│   │       ├── models.py           # Model routes
│   │       ├── providers.py        # Provider routes
│   │       ├── stats.py            # Statistics routes
│   │       └── misc.py             # Miscellaneous routes
│   ├── config.py                   # Configuration loading
│   ├── storage.py                  # AES-256-GCM encrypted storage
│   ├── errors.py                   # Structured error codes
│   ├── api_models.py               # Pydantic models
│   ├── parser.py                   # JSON import + path validation
│   ├── detector.py                 # Smart provider detection
│   ├── validator.py                # Concurrent validation engine
│   ├── checker.py                  # Retry wrapper
│   ├── tester.py                   # Capability testing
│   ├── ssrf.py                     # SSRF protection
│   ├── logger.py                   # Logging system
│   ├── proxy.py                    # Proxy detection
│   ├── webhook.py                  # Webhook notifications
│   ├── i18n.py                     # Internationalization
│   ├── model_capabilities.py       # Model capability detection
│   └── providers/                  # 45+ provider implementations
│       ├── __init__.py             # Registry
│       ├── base.py                 # ABC interface
│       ├── openai.py               # OpenAI
│       ├── anthropic.py            # Anthropic
│       └── ...                     # More providers
├── static/                         # Frontend static assets (v4.0.0 refactor)
│   ├── css/
│   │   ├── tokens.css              # CSS variables
│   │   ├── base.css                # Base styles
│   │   ├── components.css          # Component entry (@import)
│   │   ├── components/             # Individual component styles
│   │   │   ├── button.css          # Buttons
│   │   │   ├── form.css            # Form controls
│   │   │   ├── card.css            # Cards, action areas
│   │   │   ├── table.css           # Tables, badges, pagination
│   │   │   ├── stat.css            # Stat cards
│   │   │   ├── nav.css             # Navigation tabs
│   │   │   └── overlay.css         # Progress, Toast, logs
│   │   ├── modals.css              # Modal styles
│   │   └── animations.css          # Animations
│   └── js/
│       ├── state.js                # Global state
│       ├── utils.js                # Utility functions
│       ├── api/                    # API modules
│       │   ├── client.js           # Common fetch logic
│       │   ├── index.js            # Re-exports
│       │   ├── stats.js            # Statistics API
│       │   ├── keys.js             # Keys API
│       │   ├── check.js            # Validation API
│       │   ├── test.js             # Testing API
│       │   ├── balance.js          # Balance API
│       │   ├── models.js           # Models API
│       │   ├── providers.js        # Providers API
│       │   └── misc.js             # Miscellaneous API
│       ├── toast.js                # Toast notifications
│       ├── progress.js             # Progress overlay
│       ├── confirm.js              # Confirmation modal
│       ├── keys-table.js           # Table rendering
│       ├── providers.js            # Provider grid
│       ├── batch.js                # Batch results
│       ├── modals.js               # Modals
│       ├── model-detect.js         # Model detection
│       └── init.js                 # Entry point
├── templates/
│   └── index.html                  # Web UI entry (467 lines)
├── tests/                          # Test suite
│   ├── conftest.py                 # Shared fixtures and helpers
│   ├── test_detector.py            # Provider detection tests
│   ├── test_parser.py              # Parser tests
│   ├── test_validator.py           # Validator tests
│   ├── test_checker.py             # Checker tests
│   ├── test_providers.py           # Provider contract tests
│   ├── test_security.py            # Security regression tests
│   ├── test_storage.py             # Encrypted storage tests
│   ├── test_errors.py              # Error system tests
│   ├── test_i18n.py                # Internationalization tests
│   ├── test_e2e.py                 # End-to-end tests
│   ├── test_webhook.py             # Webhook tests
│   ├── test_bug_fixes.py           # Bug fix regression tests
│   └── test_provider_refactoring.py # Provider refactoring tests
├── sdk/                            # SDK
│   ├── python/                     # Python SDK
│   └── typescript/                 # TypeScript SDK
├── config.yaml                     # Configuration file
├── pyproject.toml                  # Project configuration
├── main.py                         # CLI entry point
└── web.py                          # Web entry point
```

## Configuration

Edit `config.yaml`:

```yaml
# Proxy settings
proxy: "http://127.0.0.1:7890"  # or socks5://127.0.0.1:7890

# Validation settings
check:
  concurrency: 100              # Concurrency
  timeout_seconds: 30           # Timeout
  retry_failed: true            # Retry on failure
  retry_count: 2                # Retry count

# Testing settings
test:
  token_steps:
    - 1024
    - 4096
    - 16384
    - 65536
  concurrency_steps:
    - 1
    - 5
    - 10
    - 20

# Storage settings
storage:
  keys_file: "./data/keys.json"
  encrypted: true  # Set to false to disable encryption and store in plaintext (useful for local development)

# Authentication settings
auth:
  api_key: "your-secret-api-key"  # API authentication

# Rate limiting
rate_limit:
  requests_per_minute: 60
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/keys` | Get key list |
| GET | `/api/keys/export` | Export valid keys |
| POST | `/api/import` | Import keys |
| POST | `/api/import/upload` | Upload JSON file to import |
| POST | `/api/check/single` | Validate a single key |
| POST | `/api/check/batch` | Batch validation |
| POST | `/api/test/single` | Test a single key |
| POST | `/api/test/token` | Test token limits |
| POST | `/api/test/concurrency` | Test concurrency capabilities |
| GET | `/api/models` | Get model list |
| POST | `/api/models/check` | Detect available models (SSE stream) |
| GET | `/api/providers` | Get provider list |
| GET | `/api/stats` | Get statistics |
| GET | `/api/logs` | Get logs |
| POST | `/api/webhooks` | Create webhook |
| GET | `/docs` | Swagger UI documentation |
| GET | `/redoc` | Redoc documentation |

## Webhook Usage

### Supported Event Types

| Event | Description |
|-------|-------------|
| `key.imported` | Key import completed |
| `key.checked` | Key validation completed |
| `key.tested` | Key testing completed |
| `key.deleted` | Key deleted |
| `batch.check.completed` | Batch validation completed |
| `batch.test.completed` | Batch testing completed |
| `error.occurred` | Error occurred |

### Configure Webhook

```yaml
webhooks:
  - url: "https://example.com/webhook"
    events:
      - "key.imported"
      - "key.checked"
    secret: "your-webhook-secret"  # HMAC-SHA256 signature
    active: true
    max_retries: 3
```

### Signature Verification

```python
import hmac
import hashlib
import json

def verify_signature(payload, secret, signature):
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    expected = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature == f"sha256={expected}"
```

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific tests
python -m pytest tests/test_security.py -v
python -m pytest tests/test_detector.py -v

# Run tests with coverage
python -m pytest tests/ --cov=key_manager --cov-report=term-missing
```

### Test Coverage

| Module | Test File | Test Count |
|--------|-----------|------------|
| Detection Logic (Unit) | `test_detector_unit.py` | 31 |
| Detection Logic (Endpoint) | `test_provider_detection.py` | — |
| Test Routes | `test_routes_test.py` | 48 |
| Provider Routes | `test_routes_providers.py` | 32 |
| Misc Routes | `test_routes_misc.py` | 26 |
| Model Routes | `test_routes_models.py` | 34 |
| Check Routes | `test_routes_check.py` | 23 |
| Provider Contract | `test_providers.py` | 220 |
| Key Parsing | `test_parser.py` | 24 |
| Security Regression | `test_security.py` | 21 |
| Encrypted Storage | `test_storage.py` | 26 |
| Error System | `test_errors.py` | 28 |
| Internationalization | `test_i18n.py` | 37 |
| Webhook | `test_webhook.py` | 35 |
| End-to-End | `test_e2e.py` | 18 |
| Proxy Detection | `test_proxy.py` | 19 |
| Logging System | `test_logger.py` | 21 |
| Core Facade | `test_core.py` | 22 |
| Bug Fixes | `test_bug_fixes.py` | 15 |
| Provider Refactoring | `test_provider_refactoring.py` | 32 |

**Total Tests**: 913 | **Coverage**: 92.09%

## SDK Usage

### Python SDK

```bash
cd sdk/python
pip install -e .
```

```python
from key_manager_sdk import KeyManagerClient

client = KeyManagerClient(base_url="http://localhost:18001")

# Get key list
keys = client.keys()

# Validate a single key
result = client.check_single(key="sk-xxx", provider="openai")
```

### TypeScript SDK

```bash
cd sdk/typescript
npm install
```

```typescript
npm install @api-key-manager/sdk

const client = new KeyManagerClient({ baseUrl: 'http://localhost:18001' });

// Get key list
const keys = await client.keys();

// Validate a single key
const result = await client.checkSingle({ key: 'sk-xxx', provider: 'openai' });
```

## Dependencies

- Python 3.10+
- httpx - Async HTTP client
- FastAPI - Web framework
- uvicorn - ASGI server
- PyYAML - Configuration parsing
- Rich - Terminal beautification
- cryptography - Encrypted storage
- pydantic - Data validation

## Known Issues and Limitations

### 1. Proxy Provider Misidentification

Because some proxy providers (such as Z.AI, DMXAPI, OCoolAI, etc.) use the same API endpoints and models as the original providers, when a key is invalid, the error response may contain signature keywords from the original provider, causing misidentification.

For example: A SiliconFlow key, if sent to the Alibaba Cloud endpoint, Alibaba Cloud will return an error response containing "model-studio" and "apikey-error", which may cause the system to incorrectly identify the key as belonging to Alibaba Cloud.

**Solution**: The system requires at least 2 signature matches (200 points) before returning an identification result, reducing false positives.

### 2. Limitations of Signature Matching

Signature matching relies on keywords in the error response bodies returned by providers. If a provider changes its error message format, the signatures may become invalid.

**Recommendation**: Regularly run the `verify_signatures.py` script to verify signature validity.

### 3. Timeout Issues with Concurrent Detection

During full concurrent probing, some providers may respond slowly (exceeding the 10-second timeout). This may cause valid providers to be skipped.

**Solution**: The system retries failed models serially (up to 2 times).

### 4. Dual Detection for Zhipu/Z.AI Keys

Zhipu and Z.AI use the same GLM models and API format, but use different base URLs:

- Zhipu: `https://open.bigmodel.cn/api/paas/v4`
- Z.AI: `https://api.z.ai/api/paas/v4`

The same key may work on both platforms, and the system will return the first provider that responds with 200.

### 5. Model List Timeliness

Model lists are synced from [models.dev](https://models.dev), updated once daily. Newly released models may need to wait for the next sync before they can be detected.

## Expected Design Decisions (Security Review Notes)

> **Important**: The following design decisions are **intentional**, not security vulnerabilities. Security review tools may flag these behaviors, but they are reasonable designs for this project as a **local API key management tool**.

### 1. Authentication Disabled by Default

**Behavior**: When `api_key` or `KEY_MANAGER_API_KEY` is not configured, all API endpoints can be accessed without authentication.

**Reason**: This is a local development tool, and users may not have configured authentication on first run. The system automatically derives an API token from the encryption key, ensuring basic security even with an encryption key present.

**Configuration**:
```bash
# Method 1: Environment variable
set KEY_MANAGER_API_KEY=your-api-key

# Method 2: config.yaml
auth:
  api_key: "your-api-key"
```

### 2. API Token Injection into HTML

**Behavior**: `window.__API_TOKEN__` is injected into the `<head>` of `templates/index.html`.

**Reason**: Frontend JavaScript needs to call the API and must carry an authentication token. This is standard practice for single-page applications, ensuring the frontend can automatically carry the token without manual user configuration.

**Security Notes**:
- Token is derived from the encryption key, not a plaintext password
- Only exposed during local access (`localhost:18001`)
- Production environments should configure a reverse proxy and HTTPS

### 3. Full Key Retrieval Endpoint

**Behavior**: `POST /api/keys/get-full-key` returns the unmasked full API key.

**Reason**: Users need to copy the full key for use in other applications. This is a core feature of a key management tool.

**Security Measures**:
- Requires authentication (Bearer token)
- Queries via `key_masked`, does not directly expose the key list
- Audit log recorded

### 4. Unbounded Rate Limit Storage Growth

**Behavior**: The `_RATE_LIMIT_STORE` dictionary stores request records for all IPs in memory, with no maximum entry limit.

**Reason**: This is a local tool, typically accessed by only a few clients. DDoS attack scenarios are unrealistic (internal use).

**Mitigations**:
- Cleans up IPs inactive for more than 5 minutes every 60 seconds
- Rate limiting can be disabled via `rate_limit.requests_per_minute: 0`

### 5. Middleware Execution Order

**Behavior**: Middleware order is `rate_limit → auth → i18n`, and unauthenticated requests consume rate limit quota.

**Reason**: This is an internal tool, and attacker scenarios are unrealistic. Order adjustments have minimal impact on normal usage.

**Note**: Even unauthenticated requests should be rate-limited to prevent accidental bulk requests (such as loop requests caused by frontend bugs).

### 6. Empty Data Returned When File Does Not Exist

**Behavior**: When the `keys.json` file does not exist, `_load_keys_data()` returns `{"keys": {}}` instead of throwing an exception.

**Reason**: On first run, the key file has not been created yet, which is a valid state. The system should handle this gracefully instead of crashing.

**Implementation**: Check if the file exists before calling `KeyStore.load()`:
```python
def _load_keys_data(config_override: dict | None = None) -> dict:
    cfg = config_override or config
    keys_path = Path(cfg["storage"]["keys_file"])
    if not keys_path.exists():
        return {"keys": {}}
    # ... continue with existing logic
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

## License

MIT License

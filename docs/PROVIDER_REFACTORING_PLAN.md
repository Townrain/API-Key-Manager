# Provider System Refactoring Plan — API Key Manager

## Context

**Current State**: 46 providers with ~2100 lines of duplicated code across 35 standard OpenAI-compatible providers. Adding a new provider requires editing 5 files with 6+ separate dict entries. No plugin system, no configuration-driven provider definitions.

**Root Cause**: `test_token_limit` and `test_concurrency` are abstract in `ProviderBase`, forcing every provider to implement near-identical logic. Metadata (display names, error signatures, prefixes, websites) lives in 4 separate dicts across 2 files instead of on the provider classes.

**Goal**: Reduce new-provider creation to a single file with ~15 lines. Enable config-driven custom providers. Support runtime configuration via Web/CLI. Maintain 100% backward compatibility.

**Key Insight**: Every provider's core is a set of controllable variables (base_url, check_endpoint, check_model, etc.). Users should be able to modify these via Web UI or CLI, with changes persisted to config.

---

## Architecture Design

### Class Hierarchy (After Refactoring)

```
ProviderBase (ABC)                     ← base.py (unchanged interface, new defaults)
├── name: str (abstract)               ← already abstract
├── base_url: str (abstract)           ← already abstract
├── check_endpoint: str (abstract)     ← already abstract
├── build_headers(key) (abstract)      ← already abstract
├── check_model: str                   ← already exists, default "gpt-3.5-turbo"
├── display_name: str                  ← NEW class attr, default = name
├── key_prefixes: list[str]            ← NEW class attr, default = []
├── error_signatures: list[str]        ← NEW class attr, default = []
├── website_url: str                   ← NEW class attr, default = ""
├── docs_url: str                      ← NEW class attr, default = ""
├── chat_endpoint: str                 ← NEW, default "/chat/completions"
│
├── check(client, key) → CheckResult   ← existing concrete, unchanged
├── probe(client, key) → CheckResult   ← existing concrete, unchanged
├── get_models(client, key) → list     ← existing concrete, unchanged
├── get_balance(client, key) → Balance ← existing concrete, unchanged
│
├── test_token_limit(client, key, steps) → TestResult   ← MOVED from abstract → concrete default
├── test_concurrency(client, key, steps) → TestResult   ← MOVED from abstract → concrete default
├── _probe(client, headers) → bool                      ← NEW concrete default
├── check_real(client, key) → CheckResult               ← NEW concrete default (= check)
└── test_concurrency_for_model(client, key, model, steps) ← existing concrete, unchanged
```

### New Provider File (Standard OpenAI-Compatible)

```python
# providers/deepseek.py — AFTER refactoring (15 lines vs current 133 lines)
from .base import ProviderBase

class DeepSeekProvider(ProviderBase):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
    check_endpoint = "/models"
    check_model = "deepseek-chat"
    display_name = "DeepSeek"
    key_prefixes = ["sk-"]
    error_signatures = ["authentication fails", "deepseek", "api.deepseek.com"]
    website_url = "https://platform.deepseek.com"
    docs_url = "https://platform.deepseek.com/api-docs"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}

    async def get_balance(self, client, key: str):
        # ... custom balance logic (only this provider needs it)
```

### Module Diagram (After Refactoring)

```
key_manager/providers/
├── __init__.py          ← Auto-discovery registry (replaces 292-line manual registry)
├── base.py              ← ProviderBase with concrete defaults (unchanged interface)
├── models_registry.py   ← Auto-generated model lists (unchanged)
├── config_providers.py  ← YAML config loader for custom providers (NEW)
├── openai.py            ← ~15 lines (was 101)
├── anthropic.py         ← ~40 lines (keeps custom check/test_token_limit)
├── google.py            ← ~35 lines (keeps custom auth + check)
├── deepseek.py          ← ~25 lines (keeps custom get_balance)
├── replicate.py         ← ~15 lines (overrides test_token_limit → None)
└── ...                  ← All other providers similarly reduced
```

### Auto-Discovery Registry (`__init__.py` — After)

```python
# providers/__init__.py — AFTER refactoring (~40 lines vs current 292 lines)
import pkgutil
import importlib
import logging
from .base import ProviderBase

logger = logging.getLogger(__name__)

_PROVIDER_REGISTRY: dict[str, ProviderBase] = {}

def _discover_providers() -> None:
    """Auto-discover all ProviderBase subclasses in this package."""
    package_dir = __path__
    for _finder, module_name, _ispkg in pkgutil.iter_modules(package_dir):
        if module_name in ("base", "models_registry", "config_providers"):
            continue
        try:
            mod = importlib.import_module(f".{module_name}", __package__)
            for attr_name in dir(mod):
                cls = getattr(mod, attr_name)
                if (isinstance(cls, type) and
                    issubclass(cls, ProviderBase) and
                    cls is not ProviderBase):
                    instance = cls()
                    _PROVIDER_REGISTRY[instance.name] = instance
        except Exception as e:
            logger.warning(f"Failed to load provider {module_name}: {e}")

def _load_config_providers() -> None:
    """Load custom providers from config.yaml."""
    from .config_providers import load_custom_providers
    for name, provider in load_custom_providers().items():
        if name not in _PROVIDER_REGISTRY:
            _PROVIDER_REGISTRY[name] = provider

_discover_providers()
_load_config_providers()

# Backward-compatible exports (generated from provider metadata)
PROVIDERS = _PROVIDER_REGISTRY
KEY_PREFIX_MAP = _build_key_prefix_map()
DISPLAY_NAMES = {p.name: p.display_name for p in PROVIDERS.values()}
PROVIDER_ERROR_SIGNATURES = {p.name: p.error_signatures for p in PROVIDERS.values()}
PROVIDER_WEBSITES = {p.name: {"name": p.display_name, "url": p.website_url, "docs": p.docs_url}
                     for p in PROVIDERS.values()}

def get_display_name(provider_name: str) -> str:
    return DISPLAY_NAMES.get(provider_name, provider_name)

def _build_key_prefix_map() -> dict[str, list[str]]:
    result = {}
    for p in PROVIDERS.values():
        for prefix in p.key_prefixes:
            result.setdefault(prefix, []).append(p.name)
    return dict(sorted(result.items(), key=lambda x: -len(x[0])))
```

### YAML Config Format (Custom Providers)

```yaml
# config.yaml — providers section (NEW)
providers:
  custom:
    - name: "my-llm"
      base_url: "https://api.my-llm.com/v1"
      check_endpoint: "/models"
      check_model: "my-model"
      display_name: "My LLM Provider"
      key_prefixes: ["myllm-"]
      error_signatures: ["my-llm", "invalid api key"]
      website_url: "https://my-llm.com"
      docs_url: "https://docs.my-llm.com"
      auth_type: bearer  # bearer | x-api-key | query_param
      chat_endpoint: "/chat/completions"
```

### Runtime Configuration (Web/CLI)

Users can modify provider variables at runtime via Web UI or CLI. Changes are persisted to `data/provider_overrides.json` and merged with defaults at load time.

#### Controllable Variables

| Variable | Type | Description | Example |
|----------|------|-------------|---------|
| `base_url` | str | API base URL | `https://api.deepseek.com` |
| `check_endpoint` | str | Model list endpoint | `/v1/models` |
| `chat_endpoint` | str | Chat completion endpoint | `/chat/completions` |
| `check_model` | str | Default model for testing | `deepseek-chat` |
| `display_name` | str | Human-readable name | `DeepSeek` |
| `key_prefixes` | list[str] | Key prefixes for detection | `["sk-"]` |
| `error_signatures` | list[str] | Error body substrings | `["authentication fails"]` |
| `website_url` | str | Provider website | `https://platform.deepseek.com` |
| `docs_url` | str | Documentation URL | `https://platform.deepseek.com/api-docs` |
| `auth_type` | str | Auth method | `bearer` / `x-api-key` / `query_param` |
| `enabled` | bool | Enable/disable provider | `true` |

#### Storage Format (`data/provider_overrides.json`)

```json
{
  "deepseek": {
    "base_url": "https://custom-deepseek.example.com",
    "check_model": "deepseek-v3"
  },
  "my-custom-llm": {
    "name": "my-custom-llm",
    "base_url": "https://api.my-llm.com/v1",
    "check_endpoint": "/models",
    "check_model": "my-model",
    "display_name": "My Custom LLM",
    "key_prefixes": ["myllm-"],
    "error_signatures": ["my-llm"],
    "auth_type": "bearer",
    "enabled": true
  }
}
```

#### Web API Endpoints

```
GET    /api/providers                    # List all providers with current config
GET    /api/providers/{name}             # Get single provider config
PUT    /api/providers/{name}             # Update provider variables
POST   /api/providers                    # Add new custom provider
DELETE /api/providers/{name}             # Remove custom provider
POST   /api/providers/{name}/reset       # Reset to defaults
```

#### CLI Commands

```bash
# List providers
python main.py providers list

# Show provider config
python main.py providers show deepseek

# Update provider variable
python main.py providers set deepseek base_url https://custom.example.com
python main.py providers set deepseek check_model deepseek-v3

# Add custom provider
python main.py providers add my-llm \
  --base-url https://api.my-llm.com/v1 \
  --check-endpoint /models \
  --check-model my-model \
  --auth-type bearer

# Remove custom provider
python main.py providers remove my-llm

# Reset provider to defaults
python main.py providers reset deepseek
```

#### Merge Logic

At load time, provider config is merged:

```
final_config = merge(code_defaults, provider_overrides.json)
```

Priority: `provider_overrides.json` > `config.yaml providers.custom` > `code defaults`

```python
def _load_provider_config(provider_name: str) -> dict:
    """Merge provider config from multiple sources."""
    # 1. Code defaults (from class attributes)
    defaults = get_class_defaults(provider_name)
    
    # 2. YAML custom providers
    yaml_config = get_yaml_custom(provider_name)
    
    # 3. Runtime overrides (highest priority)
    overrides = get_runtime_overrides(provider_name)
    
    return deep_merge(defaults, yaml_config, overrides)
```

---

## Task Dependency Graph

| Task | Depends On | Reason |
|------|------------|--------|
| T1: Add default implementations to ProviderBase | None | Foundation — moves abstract methods to concrete |
| T2: Add metadata class attributes to ProviderBase | None | Foundation — defines the new interface |
| T3: Migrate standard providers to use defaults | T1, T2 | Needs the new base class to exist |
| T4: Migrate non-standard providers | T1, T2 | Needs new base, keeps custom overrides |
| T5: Build auto-discovery registry | T3, T4 | Needs all providers to have metadata |
| T6: Build backward-compatible exports | T5 | Needs registry to generate dicts |
| T7: Remove duplicate dicts from detector.py | T6 | Needs PROVIDER_ERROR_SIGNATURES to exist |
| T8: Add YAML config loader | T5 | Extends the registry with custom providers |
| T9: Update tests | T6 | Tests need backward-compatible PROVIDERS dict |
| T10: Update docs/ADD_PROVIDER.md | T6 | Documents the new way to add providers |
| T11: Clean up imports in web.py, validator.py, tester.py | T6 | Verify backward compatibility |
| T12: Run full test suite + lint | T9, T11 | Final verification |

## Parallel Execution Graph

```
Wave 1 (Start immediately — no dependencies):
├── T1: Add default implementations to ProviderBase (test_token_limit, test_concurrency, _probe, check_real)
└── T2: Add metadata class attributes to ProviderBase (display_name, key_prefixes, error_signatures, etc.)

Wave 2 (After Wave 1):
├── T3: Migrate 35 standard providers to use base defaults (~2100 lines removed)
├── T4: Migrate 11 non-standard providers (anthropic, google, cohere, replicate, huggingface, + balance providers)

Wave 3 (After Wave 2):
├── T5: Build auto-discovery registry in __init__.py
└── T8: Add YAML config loader for custom providers

Wave 4 (After Wave 3):
├── T6: Build backward-compatible exports (PROVIDERS, KEY_PREFIX_MAP, DISPLAY_NAMES, etc.)
└── T7: Remove UNIQUE_SIGNATURES from detector.py, use PROVIDER_ERROR_SIGNATURES

Wave 5 (After Wave 4):
├── T9: Update/verify all tests pass
├── T10: Update docs/ADD_PROVIDER.md
└── T11: Verify web.py, validator.py, tester.py imports still work

Wave 6 (After Wave 5):
└── T12: Full test suite + lint + type check
```

**Critical Path**: T1/T2 → T3 → T5 → T6 → T9 → T12
**Estimated Parallel Speedup**: ~50% faster than sequential (Waves 1, 3, 5 have parallel tasks)

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Auto-discovery misses a provider | Low | High | Contract test catches it — `test_providers.py` parametrizes over PROVIDERS dict |
| Non-standard provider behavior changes | Medium | High | T4 keeps custom overrides; behavioral tests verify |
| web.py imports break | Low | Medium | Backward-compatible exports in T6; import verification in T11 |
| Detection behavior changes | Medium | High | T7 preserves exact same signature data; test_detector.py verifies |
| Performance regression in provider loading | Low | Low | pkgutil runs once at import time; negligible overhead |
| Custom YAML providers break SSRF protection | Medium | High | config_providers.py must validate domains through ssrf.py |

**Highest Risk**: Task 5 (auto-discovery) — this is the single point where the registration mechanism changes. Mitigated by: keeping backward-compatible exports, running full test suite, and making it independently revertable.

---

## Success Criteria

1. **Code reduction**: ~2100 lines of duplicate code removed
2. **New provider creation**: Single file, ~15 lines (was 5 files, ~76 lines)
3. **Backward compatibility**: All 583+ tests pass, all API endpoints work
4. **Custom providers**: YAML config-driven provider addition works
5. **Coverage**: ≥85% test coverage maintained
6. **Zero breaking changes**: All existing imports, APIs, and behaviors preserved

---

## Commit Strategy

Atomic commits per task, TDD-oriented:

```
Commit 1: "refactor(providers): add concrete defaults to ProviderBase for test_token_limit, test_concurrency, _probe, check_real"
  - Changes: base.py only
  - Tests: existing test_providers.py must pass (backward compat)

Commit 2: "refactor(providers): add metadata class attributes to ProviderBase"
  - Changes: base.py only
  - Tests: existing test_providers.py must pass

Commit 3: "refactor(providers): migrate standard providers to use base defaults"
  - Changes: 35 provider files
  - Tests: test_providers.py (220 parametrized tests) must pass

Commit 4: "refactor(providers): migrate non-standard providers with metadata"
  - Changes: 11 provider files
  - Tests: test_providers.py + test_provider_detection.py must pass

Commit 5: "refactor(providers): replace manual registry with auto-discovery"
  - Changes: providers/__init__.py
  - Tests: ALL tests must pass (this is the breaking-change risk point)

Commit 6: "refactor(providers): eliminate duplicate dicts from detector.py"
  - Changes: detector.py
  - Tests: test_detector.py + test_provider_detection.py must pass

Commit 7: "feat(providers): add YAML config loader for custom providers"
  - Changes: providers/config_providers.py, __init__.py
  - Tests: new test for config loading

Commit 8: "docs: update ADD_PROVIDER.md for new architecture"
  - Changes: docs/ADD_PROVIDER.md only
```

Each commit is independently revertable. If Commit 5 breaks something, Commits 1-4 are safe.

---

## 检测逻辑详解（重要！）

### ⚠️ 关键概念：/v1/models vs /chat/completions

**这两个端点的作用完全不同，不能混用！**

| 端点 | 作用 | 返回200的含义 |
|------|------|--------------|
| `/v1/models` | 获取模型列表 | 只表示可以获取模型列表，**不能**判断密钥是否有效 |
| `/chat/completions` | 调用模型 | 表示密钥对该提供商有效，**这才是判断提供商的依据** |

**常见错误：**
- ❌ 用 `/v1/models` 返回200来判断提供商 → 错误！
- ✅ 用 `/chat/completions` 返回200来判断提供商 → 正确！

### 检测流程

```
1. 前缀匹配 - 检查唯一前缀（如 sk-proj- → OpenAI）
2. 格式匹配 - 检查特殊格式（如智谱的 {id}.{secret} 格式）
3. 全并发探测 - 用 /chat/completions 验证提供商
4. 签名匹配 - 通过错误响应体识别提供商
```

### 检测流程图

```
输入: API Key
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 1: 前缀匹配                                            │
│   - 唯一前缀 → 直接返回（如 sk-proj- → OpenAI）              │
│   - 共享前缀 → 继续下一步                                    │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 2: 格式匹配                                            │
│   - 智谱格式 {id}.{secret} → 返回 ["zhipu", "zai"]          │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 3: 全并发探测（用 /chat/completions 验证）               │
│                                                             │
│   3.1 获取所有提供商的模型列表（/v1/models）                  │
│       - 这一步只是为了获取模型，不能判断提供商                 │
│                                                             │
│   3.2 并发测试所有（提供商，模型）对的 /chat/completions       │
│       - 第一个返回200的提供商胜出                             │
│       - 包括免费模型和付费模型                                │
└─────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────┐
│ Step 4: 签名匹配（如果 /chat/completions 都失败）             │
│   - 通过错误响应体中的关键词识别提供商                        │
│   - 需要至少2个签名匹配（200分）才返回结果                    │
└─────────────────────────────────────────────────────────────┘
```

### 免费模型的重要性

**某些提供商（如 OpenCode Zen）提供免费模型，这些模型对检测非常重要！**

```python
# OpenCode Zen 的模型列表：
# - claude-fable-5 (付费)
# - deepseek-v4-flash-free (免费) ✅
# - mimo-v2.5-free (免费) ✅

# 如果密钥只对免费模型有效：
# - /chat/completions + claude-fable-5 → 401 (付费模型，无权限)
# - /chat/completions + deepseek-v4-flash-free → 200 (免费模型，有权限) ✅
```

**检测逻辑会并发测试所有模型，包括免费模型。只要有一个模型返回200，提供商就会被正确识别。**

### 检测优先级

| 优先级 | 方法 | 端点 | 说明 |
|--------|------|------|------|
| 1 | 前缀匹配 | - | 唯一前缀，如 `sk-proj-` → OpenAI |
| 2 | 格式匹配 | - | 特殊格式，如 `{id}.{secret}` → 智谱 |
| 3 | 全并发探测 | `/chat/completions` | 第一个返回200的提供商胜出 |
| 4 | 签名匹配 | - | 通过错误响应体识别，需至少2个签名匹配 |

### 常见问题

#### Q: 为什么我的密钥被错误识别为其他提供商？

**A: 可能是因为：**
1. 密钥使用共享前缀（如 `sk-`），需要通过 `/chat/completions` 验证
2. 密钥只对免费模型有效，但检测逻辑没有测试免费模型
3. 提供商的 `/v1/models` 返回200，但 `/chat/completions` 返回401

#### Q: 为什么 `/v1/models` 返回200，但检测失败？

**A: 因为 `/v1/models` 返回200不能判断提供商！**
- `/v1/models` 只表示可以获取模型列表
- `/chat/completions` 返回200才能判断提供商

#### Q: 如何确保检测正确？

**A: 确保以下几点：**
1. 密钥对至少一个模型有调用权限（包括免费模型）
2. 提供商的 `/chat/completions` 端点正常工作
3. 密钥没有过期或被撤销

### 代码实现

检测逻辑在 `key_manager/detector.py` 中实现：

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

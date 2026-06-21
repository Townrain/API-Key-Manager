# 添加新服务商指南

本文档详细说明如何添加新的 AI 服务商到 API Key Manager。

## 目录

- [概述](#概述)
- [相关文件](#相关文件)
- [添加步骤](#添加步骤)
- [文件格式详解](#文件格式详解)
- [特殊情况处理](#特殊情况处理)
- [验证流程](#验证流程)

---

## 概述

添加新服务商需要修改以下文件：

| 文件 | 作用 | 必须 |
|------|------|------|
| `key_manager/providers/{name}.py` | 服务商实现 | ✅ |
| `key_manager/providers/__init__.py` | 注册服务商 | ✅ |
| `key_manager/providers/models_registry.py` | 静态模型列表 | ✅ |

---

## 相关文件

### 1. 服务商实现文件

**路径**: `key_manager/providers/{provider_name}.py`

**作用**: 定义服务商的 API 地址、认证方式、端点等

**是否需要自定义 `check()` 方法**:
- **标准 OpenAI 格式** (`/v1/chat/completions`): ❌ 不需要，继承 `base.py` 的三步检测
- **非标准格式** (Anthropic `/v1/messages`, Google `:generateContent` 等): ✅ 需要

### 2. 注册文件

**路径**: `key_manager/providers/__init__.py`

**作用**: 将服务商注册到系统中，包含 6 处修改

### 3. 模型注册表

**路径**: `key_manager/providers/models_registry.py`

**作用**: 提供静态模型列表（无 API Key 时使用）

---

## 添加步骤

### 第一步：创建服务商文件

创建 `key_manager/providers/{provider_name}.py`：

```python
"""{Provider Name} provider implementation."""
import asyncio
import time
from .base import ProviderBase, CheckResult, TestResult


class {ProviderName}Provider(ProviderBase):
    name = "{provider-name}"                    # 内部标识（小写，连字符分隔）
    base_url = "https://api.example.com/v1"     # API 基础地址
    check_endpoint = "/models"                   # 模型列表端点
    check_model = "default-model"               # 默认检测模型（回退用）

    def build_headers(self, key: str) -> dict:
        """构建认证头"""
        return {"Authorization": f"Bearer {key}"}

    async def get_models(self, client, key: str) -> list[str]:
        """从 API 获取模型列表"""
        headers = self.build_headers(key)
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}",
                headers=headers
            )
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data:
                    return [m["id"] for m in data["data"] if "id" in m]
            return []
        except Exception:
            return []

    # ❌ 不需要自定义 check() 方法
    # ✅ 继承 base.py 的三步检测逻辑：
    #    1. GET /v1/models → 获取模型列表
    #    2. < 10 模型 → 串行测试 /v1/chat/completions
    #    3. >= 10 模型 → 并行测试 batch_size=10

    async def test_token_limit(self, client, key: str,
                                token_steps: list[int]) -> TestResult:
        """测试 Token 上限"""
        headers = self.build_headers(key)
        headers["Content-Type"] = "application/json"
        last_success = None

        for step in token_steps:
            try:
                resp = await client.post(
                    f"{self.get_base_url()}/chat/completions",
                    headers=headers,
                    json={
                        "model": self.check_model,
                        "messages": [{"role": "user", "content": "hi"}],
                        "max_tokens": step
                    }
                )
                if resp.status_code == 200:
                    last_success = step
                elif resp.status_code in (400, 413):
                    break
                elif resp.status_code == 429:
                    await asyncio.sleep(1)
                    continue
                else:
                    break
            except Exception:
                break

        return TestResult(max_tokens=last_success)

    async def test_concurrency(self, client, key: str,
                                concurrency_steps: list[int]) -> TestResult:
        """测试并发能力"""
        headers = self.build_headers(key)
        last_success = None

        for step in concurrency_steps:
            tasks = [self._concurrency_probe(client, headers) for _ in range(step)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            rate_limited = sum(1 for r in results if not isinstance(r, Exception) and not r)
            if rate_limited / step >= 0.3:
                break
            last_success = step

        return TestResult(max_concurrency=last_success)

    async def _concurrency_probe(self, client, headers: dict) -> bool:
        """并发探测"""
        try:
            resp = await client.get(
                f"{self.get_base_url()}{self.check_endpoint}",
                headers=headers
            )
            return resp.status_code == 200
        except Exception:
            return False
```

### 第二步：注册服务商

编辑 `key_manager/providers/__init__.py`，修改 6 处：

#### 2.1 添加导入

```python
# 文件顶部
from .{provider_name} import {ProviderName}Provider
```

#### 2.2 注册到 PROVIDERS 字典

```python
PROVIDERS: dict[str, ProviderBase] = {
    # ... 其他服务商
    "{provider-name}": {ProviderName}Provider(),
}
```

#### 2.3 添加到 KEY_PREFIX_MAP

如果有唯一前缀：
```python
KEY_PREFIX_MAP: dict[str, list[str]] = {
    # ... 其他前缀
    "unique-prefix": ["{provider-name}"],
}
```

如果是通用 `sk-` 前缀：
```python
"sk-": ["openai", "deepseek", ..., "{provider-name}"],
```

#### 2.4 添加显示名称

```python
DISPLAY_NAMES: dict[str, str] = {
    # ... 其他显示名
    "{provider-name}": "显示名称",
}
```

#### 2.5 添加错误签名

```python
PROVIDER_ERROR_SIGNATURES: dict[str, list[str]] = {
    # ... 其他签名
    "{provider-name}": ["error-keyword-1", "error-keyword-2"],
}
```

**签名要求**:
- 至少 2 个独特关键词
- 来自实际 API 错误响应
- 小写格式

#### 2.6 添加网站信息

```python
PROVIDER_WEBSITES: dict[str, dict[str, str]] = {
    # ... 其他网站
    "{provider-name}": {
        "name": "显示名称",
        "url": "https://example.com",
        "docs": "https://docs.example.com"
    },
}
```

### 第三步：添加静态模型列表

编辑 `key_manager/providers/models_registry.py`：

```python
PROVIDER_MODELS: dict[str, list[str]] = {
    # ... 其他服务商
    "{provider-name}": [
        "model-1",
        "model-2",
        "model-3",
        # ... 更多模型
    ],
}
```

**模型来源**:
- 手动添加
- 或运行 `scripts/extract_models.py` 从 Cherry Studio 同步

---

## 文件格式详解

### check_endpoint 格式

| 格式 | 示例 | 说明 |
|------|------|------|
| `/models` | `base_url = ".../v1"`, `check_endpoint = "/models"` | 完整 URL: `.../v1/models` |
| `/v1/models` | `base_url = "..."`, `check_endpoint = "/v1/models"` | 完整 URL: `.../v1/models` |
| 自定义 | `base_url = "..."`, `check_endpoint = "/custom/path"` | 非标准端点 |

### build_headers 格式

```python
# Bearer Token（最常见）
def build_headers(self, key: str) -> dict:
    return {"Authorization": f"Bearer {key}"}

# API Key 头
def build_headers(self, key: str) -> dict:
    return {"x-api-key": key}

# 自定义头
def build_headers(self, key: str) -> dict:
    return {
        "Authorization": f"Bearer {key}",
        "anthropic-version": "2023-06-01"
    }
```

### check_model 选择

| 场景 | 推荐模型 |
|------|----------|
| 有免费模型 | 使用免费模型（如 `deepseek-v4-flash-free`） |
| 无免费模型 | 使用最便宜的模型 |
| 不确定 | 使用 `gpt-3.5-turbo`（回退值） |

---

## 特殊情况处理

### 1. 非标准 API 格式

如果服务商使用非 OpenAI 格式（如 Anthropic 的 `/v1/messages`），需要：

1. **保留自定义 `check()` 方法**
2. **在 `base.py` 的 `SKIP_MODELS_ENDPOINT` 中添加**（如果 `/v1/models` 不验证 key）

```python
# base.py 中的跳过列表
SKIP_MODELS_ENDPOINT = {"replicate", "huggingface", "ppio", "nvidia", "modelscope"}
```

### 2. /v1/models 不验证 Key

某些服务商的 `/v1/models` 返回 200 即使 Key 无效：

| 服务商 | 问题 | 处理 |
|--------|------|------|
| ppio | `/v1/models` 不验证 key | 加入 `SKIP_MODELS_ENDPOINT` |
| nvidia | `/v1/models` 不验证 key | 加入 `SKIP_MODELS_ENDPOINT` |
| modelscope | `/v1/models` 不验证 key | 加入 `SKIP_MODELS_ENDPOINT` |

### 3. 无 /v1/models 端点

某些服务商没有模型列表端点：

| 服务商 | 问题 | 处理 |
|--------|------|------|
| replicate | 使用 `/v1/account` | 加入 `SKIP_MODELS_ENDPOINT` |
| huggingface | 使用 `/api/whoami-v2` | 加入 `SKIP_MODELS_ENDPOINT` |

### 4. 非标准模型端点路径

| 服务商 | 实际端点 | 处理 |
|--------|----------|------|
| google | `/v1beta/models` | 设置 `check_endpoint = "/v1beta/models"` |
| groq | `/openai/v1/models` | 设置 `check_endpoint = "/openai/v1/models"` |
| fireworks | `/inference/v1/models` | 设置 `check_endpoint = "/inference/v1/models"` |

---

## 验证流程

### 1. 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_providers.py -v
python -m pytest tests/test_base_check.py -v
```

### 2. 检查注册

```bash
python -c "
from key_manager.providers import PROVIDERS
from key_manager.providers.models_registry import PROVIDER_MODELS

print('Provider registered:', '{provider-name}' in PROVIDERS)
print('Models count:', len(PROVIDER_MODELS.get('{provider-name}', [])))
"
```

### 3. 手动测试

```bash
# 启动 Web 服务
python web.py

# 测试 Key 检测
curl -X POST http://localhost:18001/api/check/single \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-test-key", "provider": "{provider-name}"}'
```

---

## 完整检查清单

- [ ] 创建 `providers/{name}.py`
- [ ] 设置 `name`, `base_url`, `check_endpoint`, `check_model`
- [ ] 实现 `build_headers()`
- [ ] 实现 `get_models()`（如果支持）
- [ ] 实现 `test_token_limit()`
- [ ] 实现 `test_concurrency()`
- [ ] 在 `__init__.py` 中导入
- [ ] 添加到 `PROVIDERS` 字典
- [ ] 添加到 `KEY_PREFIX_MAP`
- [ ] 添加到 `DISPLAY_NAMES`
- [ ] 添加到 `PROVIDER_ERROR_SIGNATURES`
- [ ] 添加到 `PROVIDER_WEBSITES`
- [ ] 在 `models_registry.py` 中添加模型列表
- [ ] 运行测试通过
- [ ] 手动测试 Key 检测

---

## 示例：添加 OpenCode Go

### 1. 创建 `providers/opencode.py`

```python
class OpenCodeGoProvider(ProviderBase):
    name = "opencode-go"
    base_url = "https://opencode.ai/zen/go"
    check_endpoint = "/v1/models"
    # check_model 不需要，/v1/models 返回的模型中包含免费模型

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}
```

### 2. 注册到 `__init__.py`

```python
# 导入
from .opencode import OpenCodeGoProvider

# PROVIDERS
"opencode-go": OpenCodeGoProvider(),

# KEY_PREFIX_MAP（加入 sk- 列表）
"sk-": [..., "opencode-go"],

# DISPLAY_NAMES
"opencode-go": "OpenCode Go",

# PROVIDER_ERROR_SIGNATURES
"opencode-go": ["opencode.ai", "zen/go", "creditserror", "no payment method"],

# PROVIDER_WEBSITES
"opencode-go": {"name": "OpenCode Go", "url": "https://opencode.ai", "docs": "https://opencode.ai/docs/zh-cn/go/"},
```

### 3. 添加模型列表

```python
# models_registry.py
"opencode-go": [
    "glm-5.1", "glm-5", "kimi-k2.7-code", "kimi-k2.6",
    "mimo-v2.5", "mimo-v2.5-pro", "minimax-m3", "minimax-m2.7",
    "qwen3.7-max", "qwen3.7-plus", "qwen3.6-plus",
    "deepseek-v4-pro", "deepseek-v4-flash"
],
```

---

## 三步检测逻辑详解

所有标准格式服务商（非 anthropic/google/cohere）统一使用 `base.py` 的 `check()` 方法：

### 第一步：获取模型列表（并发）

```python
# 并发调用所有服务商的 /v1/models（5秒超时）
async def get_provider_models(name, provider):
    resp = await asyncio.wait_for(
        client.get(f"{provider.get_base_url()}{provider.check_endpoint}", ...),
        timeout=5.0
    )
    if resp.status_code == 200:
        return name, [m["id"] for m in data["data"]]
    return name, []

# 所有服务商并发调用
model_tasks = [get_provider_models(name, provider) for name, provider in PROVIDERS.items()]
model_results = await asyncio.gather(*model_tasks)
```

**跳过条件**：
- `/v1/models` 返回空 → 跳过该服务商
- 超时 5 秒 → 跳过该服务商

### 第二步：并发测试所有模型

```python
# 从 check_endpoint 提取版本路径
# "/v1/models" → "/v1"
version_match = re.match(r'(/v\d+)', provider.check_endpoint or '')
version_prefix = version_match.group(1) if version_match else ''
chat_url = f"{provider.get_base_url()}{version_prefix}/chat/completions"

# 所有模型并发测试（5秒超时）
tasks = [test_model(m) for m in models]
results = await asyncio.gather(*tasks)

# 返回第一个成功的
for result in results:
    if result.valid:
        return result
```

---

## 常见问题

### Q: 为什么我的服务商检测不到？

A: 检查以下几点：
1. 是否添加到 `KEY_PREFIX_MAP`
2. 错误签名是否足够独特
3. `/v1/models` 是否验证 key

### Q: 为什么检测到了但显示无效？

A: 可能原因：
1. `check_model` 是付费模型，账户欠费
2. 使用免费模型作为 `check_model`

### Q: 如何添加非标准格式的服务商？

A: 参考 `anthropic.py` 或 `google.py`，保留自定义 `check()` 方法。

---

## 更新日志

- **v2.2.0** (2026-06-14):
  - 添加三步检测逻辑，统一标准格式服务商
  - 修复 URL 构造：从 check_endpoint 提取版本路径
  - 并发优化：/v1/models 和 chat/completions 都并发调用
  - 超时控制：所有网络请求 5 秒超时
  - 移除无用的 check_model（有 /v1/models 端点的服务商）
- **v2.1.1** (2026-06-11): 初始版本

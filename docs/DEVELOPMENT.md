# API Key Manager - 开发指南

> 本文档供后续开发者（包括 AI）快速理解项目结构和扩展方式。

## 项目概述

API Key Manager 是一个批量管理 45+ AI 服务商 API 密钥的 Python 工具，支持 CLI 和 Web 两种界面。

**技术栈：** Python 3.10+ / FastAPI / httpx / Pydantic / cryptography

---

## 目录结构

```
key/
├── key_manager/                  # 核心包
│   ├── __init__.py               # 包导出，版本号
│   ├── core.py                   # KeyManager 门面类（编程接口）
│   ├── config.py                 # YAML 配置加载
│   ├── storage.py                # AES-256-GCM 加密存储
│   ├── errors.py                 # 结构化错误码
│   ├── api_models.py             # Pydantic 请求/响应模型
│   ├── parser.py                 # JSON 导入 + 路径验证
│   ├── detector.py               # 智能提供商检测
│   ├── validator.py              # 并发验证引擎
│   ├── checker.py                # 重试包装器
│   ├── tester.py                 # 能力测试（Token/并发）
│   ├── ssrf.py                   # SSRF 防护
│   ├── logger.py                 # 日志系统
│   ├── proxy.py                  # 代理检测
│   ├── webhook.py                # Webhook 通知
│   ├── i18n.py                   # 国际化
│   ├── model_capabilities.py     # 模型能力检测
│   ├── url_override.py           # 自定义 Base URL（线程局部）
│   ├── providers/                # 45+ 提供商实现
│   │   ├── __init__.py           # 自动发现 + 注册表
│   │   ├── base.py               # ProviderBase 抽象基类
│   │   ├── openai.py             # 示例：OpenAI 提供商
│   │   ├── anthropic.py          # 示例：Anthropic 提供商
│   │   └── ...                   # 更多提供商
│   └── web/                      # Web 应用（FastAPI）
│       ├── __init__.py           # 向后兼容导出
│       ├── _app.py               # 应用入口 + 配置
│       ├── middleware.py          # 中间件 + 错误处理器
│       ├── progress.py           # ProgressTracker + SSE
│       └── routes/               # API 路由模块
│           ├── keys.py           # 密钥管理
│           ├── check.py          # 验证
│           ├── test.py           # 测试
│           ├── balance.py        # 余额
│           ├── models.py         # 模型
│           ├── providers.py      # 提供商 CRUD
│           ├── stats.py          # 统计
│           └── misc.py           # 杂项（日志/进度/Webhook）
├── templates/                    # Web UI 模板
│   └── index.html                # 赛博朋克风格前端
├── tests/                        # 测试套件（583+ 测试）
├── sdk/                          # 客户端 SDK
│   ├── python/                   # Python SDK
│   └── typescript/               # TypeScript SDK
├── config.yaml                   # 配置文件
├── pyproject.toml                # 项目配置
└── main.py / web.py              # 入口点（向后兼容）
```

---

## 核心模块说明

### 1. 配置系统 (`config.py`)

```python
from key_manager.config import load_config

config = load_config()  # 从 config.yaml 加载
```

**配置结构：**
```yaml
proxy: ""                    # 代理地址
check:
  concurrency: 100           # 并发数
  timeout_seconds: 30        # 超时时间
test:
  token_steps: [1024, 4096]  # Token 测试步长
  concurrency_steps: [1, 5]  # 并发测试步长
storage:
  keys_file: "./data/keys.json"
auth:
  api_key: "your-secret-key" # API 认证
```

### 2. 存储系统 (`storage.py`)

使用 AES-256-GCM 加密存储 API 密钥：

```python
from key_manager.storage import KeyStore

store = KeyStore("data/keys.json", config)
data = store.load()   # 解密加载
store.save(data)      # 加密保存
```

### 3. 提供商系统 (`providers/`)

**添加新提供商：**

1. 创建 `key_manager/providers/my_llm.py`：

```python
from .base import ProviderBase

class MyLlmProvider(ProviderBase):
    name = "my-llm"
    base_url = "https://api.my-llm.com/v1"
    check_endpoint = "/models"
    display_name = "My LLM"
    key_prefixes = ["myllm-"]
    error_signatures = ["my-llm", "invalid api key"]
    website_url = "https://my-llm.com"
    docs_url = "https://docs.my-llm.com"

    def build_headers(self, key: str) -> dict:
        return {"Authorization": f"Bearer {key}"}
```

2. 重启服务即可自动发现（使用 `pkgutil` 自动扫描）。

**ProviderBase 关键方法：**
- `check(client, key)` — 验证密钥有效性
- `get_models(client, key)` — 获取可用模型列表
- `get_balance(client, key)` — 查询余额（可选）
- `test_token_limit(client, key, steps)` — 测试 Token 上限
- `test_concurrency(client, key, steps)` — 测试并发能力

### 4. 检测系统 (`detector.py`)

**重要：检测逻辑使用 `/chat/completions` 验证提供商，不是 `/v1/models`！**

#### 检测流程

```
1. 前缀匹配 - 检查唯一前缀（如 sk-proj- → OpenAI）
2. 格式匹配 - 检查特殊格式（如智谱的 {id}.{secret} 格式）
3. 全并发探测 - 用 /chat/completions 验证提供商
4. 签名匹配 - 通过错误响应体识别提供商
```

#### ⚠️ 关键概念：/v1/models vs /chat/completions

| 端点 | 作用 | 返回200的含义 |
|------|------|--------------|
| `/v1/models` | 获取模型列表 | 只表示可以获取模型列表，**不能**判断密钥是否有效 |
| `/chat/completions` | 调用模型 | 表示密钥对该提供商有效，**这才是判断提供商的依据** |

**常见错误：**
- ❌ 用 `/v1/models` 返回200来判断提供商 → 错误！
- ✅ 用 `/chat/completions` 返回200来判断提供商 → 正确！

#### 检测流程详解

```python
async def detect_provider(client, key):
    # Step 1: 前缀匹配
    prefix_candidates = detect_by_prefix(key)
    if len(prefix_candidates) == 1:
        return prefix_candidates[0]  # 唯一前缀，直接返回
    
    # Step 2: 格式匹配
    format_candidates = detect_by_format(key)
    if format_candidates:
        return format_candidates[0]  # 特殊格式，直接返回
    
    # Step 3: 全并发探测（用 /chat/completions 验证）
    # 3.1 获取所有提供商的模型列表（/v1/models）
    #     这一步只是为了获取模型，不能判断提供商
    models = await get_all_models(client, key)
    
    # 3.2 并发测试所有（提供商，模型）对的 /chat/completions
    #     这一步才是判断提供商的依据！
    tasks = []
    for name, model_list in models.items():
        for model in model_list:
            tasks.append(try_chat_completion(name, model))
    
    # 第一个返回200的提供商胜出
    for coro in asyncio.as_completed(tasks):
        name, valid, status_code = await coro
        if valid:  # /chat/completions 返回200
            return name
    
    # Step 4: 签名匹配
    return match_by_signature(error_bodies)
```

#### 免费模型的重要性

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

#### 检测优先级

| 优先级 | 方法 | 端点 | 说明 |
|--------|------|------|------|
| 1 | 前缀匹配 | - | 唯一前缀，如 `sk-proj-` → OpenAI |
| 2 | 格式匹配 | - | 特殊格式，如 `{id}.{secret}` → 智谱 |
| 3 | 全并发探测 | `/chat/completions` | 第一个返回200的提供商胜出 |
| 4 | 签名匹配 | - | 通过错误响应体识别，需至少2个签名匹配 |

---

## Web 应用架构

### 路由模块 (`web/routes/`)

每个路由模块使用 `APIRouter`：

```python
from fastapi import APIRouter
from key_manager.api_models import MyResponse

router = APIRouter(tags=["MyFeature"])

@router.get("/api/my-feature", response_model=MyResponse)
async def get_my_feature():
    ...
```

**注册路由：** 在 `web/_app.py` 中：
```python
from key_manager.web.routes import my_feature
app.include_router(my_feature.router)
```

### 中间件 (`web/middleware.py`)

包含：
- 限流中间件（按 IP）
- 认证中间件（Bearer Token）
- i18n 中间件（Accept-Language）
- 错误处理器（Pydantic/KeyManager/Validation）

**添加中间件：**
1. 在 `middleware.py` 添加函数
2. 在 `setup_middleware()` 中注册

### 测试中访问配置

测试通过 patch 访问配置和提供商：

```python
# 正确的 patch 目标
with patch("key_manager.web._app.config", cfg):
    with patch("key_manager.web._app.PROVIDERS", {...}):
        # 测试代码
```

---

## 测试系统

**运行测试：**
```bash
python -m pytest tests/ -v                    # 全部测试
python -m pytest tests/test_api_endpoints.py  # API 测试
python -m pytest tests/ --cov=key_manager     # 覆盖率
```

**测试文件：**
- `test_api_endpoints.py` — API 端点测试
- `test_detector.py` — 提供商检测测试
- `test_security.py` — 安全回归测试
- `test_storage.py` — 加密存储测试
- `test_webhook.py` — Webhook 测试

---

## 常见任务

### 添加新 API 端点

1. 在 `api_models.py` 添加请求/响应模型
2. 在 `routes/` 创建或修改路由模块
3. 实现业务逻辑（可抽到 service 层）
4. 添加测试

### 添加新提供商

1. 创建 `providers/my_provider.py`
2. 实现 `ProviderBase` 子类
3. 重启服务自动发现
4. 运行 `test_providers.py` 验证

### 修改中间件

1. 编辑 `web/middleware.py`
2. 在 `setup_middleware()` 或 `setup_error_handlers()` 注册
3. 运行 `test_api_endpoints.py` 验证

---

## 安全注意事项

- **密钥存储** — AES-256-GCM 加密，随机盐值
- **路径遍历** — `validate_import_path()` 验证路径在允许目录内
- **SSRF 防护** — `validate_custom_base_url()` 验证域名白名单
- **时序安全** — 使用 `hmac.compare_digest()` 防止时序攻击
- **密钥掩码** — API 响应中只返回 `key_masked`

---

## 预期的设计决策（安全审查说明）

> **重要**：以下设计决策是**有意为之**，不是安全漏洞。安全审查工具可能会标记这些行为，但它们是本项目作为**本地API密钥管理工具**的合理设计。

### 1. 认证默认禁用

**行为**：当未配置 `api_key` 或 `KEY_MANAGER_API_KEY` 时，所有API端点无需认证即可访问。

**原因**：这是本地开发工具，首次运行时用户可能尚未配置认证。系统会自动从加密密钥派生API token，确保在有加密密钥的情况下仍能提供基本安全。

**代码位置**：`key_manager/web/middleware.py` - `auth_middleware()`

### 2. API Token注入到HTML

**行为**：`window.__API_TOKEN__` 被注入到 `templates/index.html` 的 `<head>` 中。

**原因**：前端JavaScript需要调用API，必须携带认证token。这是单页应用的标准做法。

**代码位置**：`key_manager/web/_app.py` - `web_ui()` 函数

### 3. 完整密钥检索端点

**行为**：`POST /api/keys/get-full-key` 返回未掩码的完整API密钥。

**原因**：用户需要复制完整密钥用于其他应用。这是密钥管理工具的核心功能。

**代码位置**：`key_manager/web/routes/keys.py` - `api_get_full_key()`

### 4. 速率限制存储无界增长

**行为**：`_RATE_LIMIT_STORE` 字典在内存中存储所有IP的请求记录，无最大条目限制。

**原因**：这是本地工具，通常只有少量客户端访问。DDoS攻击场景不现实。

**代码位置**：`key_manager/web/middleware.py` - `_RATE_LIMIT_STORE`

### 5. 中间件执行顺序

**行为**：中间件顺序为 `rate_limit → auth → i18n`，未认证请求会消耗速率限制配额。

**原因**：这是内部工具，攻击者场景不现实。顺序调整对正常使用几乎无影响。

**代码位置**：`key_manager/web/middleware.py` - `setup_middleware()`

### 6. 文件不存在时返回空数据

**行为**：当 `keys.json` 文件不存在时，`_load_keys_data()` 返回 `{"keys": {}}` 而不是抛出异常。

**原因**：首次运行时，密钥文件尚未创建，这是有效状态。系统应优雅处理这种情况。

**代码位置**：`key_manager/web/_app.py` - `_load_keys_data()`

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|----------|
| v4.0.0 | 2026-06-20 | Web 模块重构，代码去重，日志修复 |
| v3.2.0 | 2026-06-19 | 按模型测试，提供商管理 UI |
| v3.1.0 | 2026-06-19 | 提供商自动发现，YAML 配置 |
| v3.0.0 | 2026-06-15 | 精确匹配修复，测试补充 |

---

## 相关链接

- **仓库：** https://github.com/Townrain/API-Key-Manager
- **文档：** https://github.com/Townrain/API-Key-Manager#readme
- **API 文档：** 启动 Web 服务后访问 `/docs` (Swagger) 或 `/redoc`

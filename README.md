# API Key Manager

批量管理 45+ AI 服务商 API 密钥的 Python 工具，支持 CLI 和 Web 两种界面。

## 功能特性

- **批量导入** - 从 JSON 文件导入 API 密钥，自动去重
- **密钥验证** - 并发验证密钥有效性，支持 45+ AI 服务商
- **能力测试** - 测试 Token 上限和并发能力
- **模型筛选** - 按类型筛选模型（推理/视觉/联网/免费/嵌入/重排/工具）
- **智能检测** - 前缀匹配 + 模式匹配 + 错误签名匹配，三级提供商自动识别
- **Web 界面** - 赛博朋克风格的管理界面
- **代理支持** - 支持 HTTP/SOCKS 代理
- **加密存储** - AES-256-GCM 加密存储 API 密钥，随机盐值
- **安全防护** - 路径遍历防护、SSRF 防护、时序安全认证
- **API 文档** - Swagger UI 和 Redoc 自动文档
- **国际化** - 支持中英文错误信息
- **SDK 支持** - Python 和 TypeScript 客户端库
- **Webhook 通知** - 事件驱动的 Webhook 通知系统

## 支持的 AI 服务商

### 国际

| 服务商 | 前缀 |
|--------|------|
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

### 中国

| 服务商 | 前缀 | 显示名 |
|--------|------|--------|
| DashScope | `sk-sp-` | 阿里百炼 |
| ModelScope | `ms-` | 魔搭 |
| Zhipu GLM | `sk-` | 智谱 |
| Kimi | `sk-` | 月之暗面 |
| MiniMax | `sk-` | MiniMax |
| SiliconFlow | `sk-` | 硅基流动 |
| Baichuan | `sk-` | 百川 |
| Yi | `sk-` | 零一万物 |
| StepFun | `sk-` | 阶跃星辰 |
| Doubao | `sk-` | 豆包 |
| Infini | `sk-` | 无问芯穹 |
| MiMo | `sk-` | 小米 |
| Tencent Hunyuan | `sk-` | 腾讯混元 |
| CSTCloud | `sk-` | 中算云 |

### 新增服务商

| 服务商 | 说明 |
|--------|------|
| LongCat | 新增 |
| AI302 | 新增 |
| PPIO | 新增 |
| DMXAPI | 新增 |
| OCoolAI | 新增 |
| ZAI | 新增 |
| MiMo Plan | 计划版 |
| MiniMax Plan | 计划版 |
| DashScope Coding | 编程版 |
| Zhipu Coding | 编程版 |
| Kimi Coding | 编程版 |
| Infini Coding | 编程版 |

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/Townrain/API-Key-Manager.git
cd key

# 安装依赖
pip install -r requirements.txt

# 安装开发依赖（含测试工具）
pip install -e ".[dev]"
```

### CLI 使用

```bash
# 导入密钥
python main.py import --file data/input/example.json
python main.py import --dir ./data/input

# 验证密钥
python main.py check
python main.py check --provider openai
python main.py check --key sk-xxx

# 测试密钥
python main.py test
python main.py test --skip-token
python main.py test --skip-concurrency

# 列出密钥
python main.py list --provider anthropic --status valid
python main.py list --status invalid

# 生成报告
python main.py report --days 7
```

### Web 界面

```bash
# 启动 Web 服务器
python web.py

# 访问以下地址：
# 主界面：http://localhost:18001
# API 文档：http://localhost:18001/docs
# Redoc：http://localhost:18001/redoc
```

## 安全特性

### 加密存储

API 密钥默认使用 AES-256-GCM 加密存储，每次加密使用随机盐值：

```bash
# 设置加密密钥（环境变量）
set KEY_MANAGER_SECRET=your-secret-key

# 启动服务
python web.py
```

加密后的 `keys.json` 格式：
```json
{
  "encrypted": true,
  "salt": "base64-encoded-random-salt",
  "nonce": "base64-encoded-nonce",
  "data": "base64-encoded-ciphertext"
}
```

### 安全防护

- **路径遍历防护** - 导入端点验证路径在允许目录内
- **SSRF 防护** - `custom_base_url` 验证域名白名单，阻止私有 IP
- **时序安全认证** - 使用 `hmac.compare_digest()` 防止时序攻击
- **认证警告** - 未配置 API Key 时启动警告
- **密钥掩码** - API 响应中只返回 `key_masked`，不暴露完整密钥

### API 认证

```bash
# 设置 API Key（环境变量）
set KEY_MANAGER_API_KEY=your-api-key

# 或在 config.yaml 中配置
# auth:
#   api_key: "your-api-key"
```

## 提供商智能检测

### 检测策略

系统采用**全并发探测**策略，自动识别 45+ 个 AI 服务商的 API 密钥。

#### 检测流程

```
1. 模式匹配 - 检查唯一前缀（如 sk-proj- → OpenAI，AIza → Google）
2. 格式匹配 - 检查特殊格式（如智谱的 {id}.{secret} 格式）
3. 全并发探测 - 同时向所有服务商发送请求（40+ 服务商 × 5 模型 = 200+ 请求）
4. 签名匹配 - 如果无200响应，通过错误响应体签名识别服务商
```

#### 全并发探测逻辑

当密钥无法通过前缀或格式识别时，系统会：

1. 从 Cherry Studio 同步的模型列表中获取每个服务商的前5个模型
2. 并发向所有服务商发送请求（每个服务商尝试5个模型）
3. 第一个返回200的服务商立即胜出
4. 如果所有请求都失败，通过签名匹配识别

```python
# 检测流程示例
async def detect_provider(client, key):
    # Step 1: 模式匹配
    pattern_match = detect_by_pattern(key)  # 如 sk-proj- → OpenAI
    if pattern_match:
        return pattern_match
    
    # Step 2: 格式匹配
    format_candidates = detect_by_format(key)  # 如 {id}.{secret} → 智谱/Z.AI
    if format_candidates:
        return format_candidates[0]
    
    # Step 3: 全并发探测
    tasks = []
    for name, provider in PROVIDERS.items():
        models = PROVIDER_MODELS.get(name, [])[:5]
        for model in models:
            tasks.append(try_model(name, model))
    
    # 第一个返回200的胜出
    for coro in asyncio.as_completed(tasks):
        name, valid, body = await coro
        if valid:
            return name
    
    # Step 4: 签名匹配
    return match_by_signature(error_bodies)
```

### 特殊密钥格式支持

#### 智谱/Z.AI 密钥格式

智谱和 Z.AI 使用 `{id}.{secret}` 格式的密钥（非 `sk-` 开头）：

```python
# 示例密钥格式
50bcde33b8774aa8a2cc1bd6d39444ae.ifriyNWRLStzpLEs

# 正则表达式匹配
ZHIPU_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9]{20,50}\.[a-zA-Z0-9]{10,50}$')
```

这种格式的密钥会被自动识别为智谱或 Z.AI（两者共享相同的 GLM 模型）。

### 错误签名匹配

当所有并发请求都失败时，系统通过错误响应体中的关键词识别服务商：

```python
UNIQUE_SIGNATURES = {
    # 国内服务商
    "dashscope": ["model-studio", "modelstudio", "apikey-error"],
    "tencent-hunyuan": ["hunyuan", "console.cloud.tencent.com"],
    "baichuan": ["baichuan-ai.com", "platform.baichuan-ai.com"],
    "minimax": ["authorized_error", "login fail"],
    "yi": ["illegal apikey"],
    "kimi": ["invalid_authentication_error"],
    "siliconflow": ["api key is invalid"],
    "stepfun": ["incorrect api key provided", "invalid_api_key"],
    "doubao": ["authenticationerror"],
    "infini": ["请使用正确的api key进行请求"],
    "zhipu": ["令牌已过期或验证不正确"],
    "mimo": ["invalid api key", "please provide valid api key"],
    # 国外服务商
    "deepseek": ["authentication fails"],
    "anthropic": ["request not allowed", "anthropic", "x-api-key"],
    "openrouter": ["missing authentication header"],
    "mistral": ["mistral", "la plateforme"],
    "replicate": ["unauthenticated", "you did not pass a valid authentication token"],
    "huggingface": ["huggingface", "hf_"],
    "fireworks": ["fireworks", "accounts/fireworks"],
    "perplexity": ["perplexity"],
    "grok": ["console.x.ai"],
    "openai": ["platform.openai.com"],
    "google": ["generativelanguage"],
    "groq": ["groq"],
}
```

#### 签名匹配算法

```python
def score_provider(provider_name, error_body, status_code):
    body = error_body.lower()
    score = 0
    weight = 100  # 每个匹配的签名加100分
    
    for sig in UNIQUE_SIGNATURES.get(provider_name, []):
        if sig.lower() in body:
            score += weight
    
    return score

# 匹配阈值：至少2个签名匹配（200分）才返回结果
if best_score >= 200:
    return best_name
```

### 检测优先级

| 优先级 | 方法 | 说明 |
||------||------|
| 1 | 模式匹配 | 唯一前缀，如 `sk-proj-` → OpenAI |
| 2 | 格式匹配 | 特殊格式，如 `{id}.{secret}` → 智谱 |
| 3 | 全并发探测 | 第一个返回200的服务商胜出 |
| 4 | 签名匹配 | 通过错误响应体识别，需至少2个签名匹配 |


## 错误信息简化

系统会自动将服务商返回的原始错误信息简化为用户友好的提示：

| 原始错误信息 | 简化后 |
|-------------|--------|
| `Access denied, please make sure your account is in good standing...` | 余额不足 |
| `Invalid API Key` | Key 无效 |
| `Authentication fails` | 认证失败 |
| `Token expired` | Key 已过期 |
| `Rate limit exceeded` | 请求过于频繁 |
| `Account suspended` | 账号被封禁 |
| `Access denied` | 无权限访问 |
| `Model does not exist` | 模型不存在 |

错误信息简化在 `base.py` 的 `simplify_error()` 函数中实现，支持：

- 基于状态码的简化（401 → Key 无效，402 → 余额不足，429 → 请求过于频繁）
- 基于关键词的模式匹配（authentication、expired、rate limit 等）
- 长错误信息截断（超过100字符时截断并添加省略号）

## 项目结构


## 模型检测

### 模型列表来源

系统从 Cherry Studio 同步模型数据，生成 `models_registry.py` 文件，包含每个服务商的静态模型列表：

```python
PROVIDER_MODELS = {
    "openai": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo", ...],
    "anthropic": ["claude-3-opus", "claude-3-sonnet", ...],
    "dashscope": ["qwen-turbo", "qwen-plus", "qwen-max", ...],
    "siliconflow": ["Qwen/Qwen2.5-7B-Instruct", ...],
    # ... 45+ 服务商
}
```

### 模型检测流程

当用户点击「检测可用模型」时：

1. 获取服务商的模型列表（优先使用 API 返回，回退到静态列表）
2. 并发检测每个模型的可用性（batch_size 动态调整）
3. 每个模型发送一个最小请求（`POST /chat/completions`，`max_tokens: 5`）
4. 返回200的模型标记为可用，其他标记为失败
5. 失败的模型会串行重试（最多2次）

```python
# 模型检测逻辑
async def check_model(http, model):
    resp = await client.post(
        f"{provider.get_base_url()}/chat/completions",
        json={"model": model, "messages": [...], "max_tokens": 5}
    )
    return model, 200 if resp.status_code == 200 else resp.status_code

# 动态并发控制
batch_size = 5  # 初始并发数
for i in range(0, len(models), batch_size):
    batch = models[i:i+batch_size]
    results = await asyncio.gather(*[check_model(http, m) for m in batch])
    
    # 全部成功 → 并发数 +1
    if all_success:
        batch_size += 1
    # 有失败 → 保持当前并发数
    
    # 失败模型串行重试
    for model in failed_models:
        _, code = await check_model(http, model)
        if code == 200:
            # 重试成功
```

### 模型能力检测

系统支持按类型筛选模型：

| 类型 | 说明 | 筛选方法 |
|------|------|----------|
| 视觉模型 | 支持图像输入 | `is_vision_model()` |
| 工具模型 | 支持函数调用 | `is_tool_model()` |
| 推理模型 | 支持思维链 | `is_reasoning_model()` |
| 联网模型 | 支持网络搜索 | `is_websearch_model()` |
| 免费模型 | 免费额度 | `is_free_model()` |
| 嵌入模型 | 文本嵌入 | `is_embedding_model()` |
| 重排模型 | 搜索重排 | `is_rerank_model()` |

能力数据从 Cherry Studio 同步，存储在 `data/model_capabilities.json` 中。

## 项目结构
```
key/
├── key_manager/                    # 核心包
│   ├── __init__.py                 # 包导出
│   ├── cli.py                      # CLI 入口
│   ├── web.py                      # FastAPI 应用
│   ├── config.py                   # 配置加载
│   ├── storage.py                  # AES-256-GCM 加密存储
│   ├── errors.py                   # 结构化错误码
│   ├── api_models.py               # Pydantic 模型
│   ├── parser.py                   # JSON 导入 + 路径验证
│   ├── detector.py                 # 智能提供商检测
│   ├── validator.py                # 并发验证引擎
│   ├── checker.py                  # 重试包装器
│   ├── tester.py                   # 能力测试
│   ├── ssrf.py                     # SSRF 防护
│   ├── logger.py                   # 日志系统
│   ├── proxy.py                    # 代理检测
│   ├── webhook.py                  # Webhook 通知
│   ├── i18n.py                     # 国际化
│   ├── model_capabilities.py       # 模型能力检测
│   └── providers/                  # 45+ 提供商实现
│       ├── __init__.py             # 注册表
│       ├── base.py                 # ABC 接口
│       ├── openai.py               # OpenAI
│       ├── anthropic.py            # Anthropic
│       └── ...                     # 更多提供商
├── tests/                          # 测试套件
│   ├── test_detector.py            # 提供商检测测试
│   ├── test_parser.py              # 解析器测试
│   ├── test_validator.py           # 验证器测试
│   ├── test_checker.py             # 检查器测试
│   ├── test_providers.py           # 提供商合约测试
│   ├── test_security.py            # 安全回归测试
│   ├── test_storage.py             # 加密存储测试
│   ├── test_errors.py              # 错误系统测试
│   ├── test_i18n.py                # 国际化测试
│   ├── test_e2e.py                 # 端到端测试
│   └── test_webhook.py             # Webhook 测试
├── sdk/                            # SDK
│   ├── python/                     # Python SDK
│   └── typescript/                 # TypeScript SDK
├── config.yaml                     # 配置文件
├── pyproject.toml                  # 项目配置
├── main.py                         # CLI 入口
└── web.py                          # Web 入口
```

## 配置说明

编辑 `config.yaml`：

```yaml
# 代理设置
proxy: "http://127.0.0.1:7890"  # 或 socks5://127.0.0.1:7890

# 验证设置
check:
  concurrency: 100              # 并发数
  timeout_seconds: 30           # 超时时间
  retry_failed: true            # 失败重试
  retry_count: 2                # 重试次数

# 测试设置
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

# 认证设置
auth:
  api_key: "your-secret-api-key"  # API 认证

# 速率限制
rate_limit:
  requests_per_minute: 60
```

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/keys` | 获取密钥列表 |
| GET | `/api/keys/export` | 导出有效密钥 |
| POST | `/api/import` | 导入密钥 |
| POST | `/api/import/upload` | 上传 JSON 文件导入 |
| POST | `/api/check/single` | 验证单个密钥 |
| POST | `/api/check/batch` | 批量验证 |
| POST | `/api/test/single` | 测试单个密钥 |
| POST | `/api/test/token` | 测试 Token 上限 |
| POST | `/api/test/concurrency` | 测试并发能力 |
| GET | `/api/models` | 获取模型列表 |
| POST | `/api/models/check` | 检测可用模型（SSE 流） |
| GET | `/api/providers` | 获取服务商列表 |
| GET | `/api/stats` | 获取统计信息 |
| GET | `/api/logs` | 获取日志 |
| POST | `/api/webhooks` | 创建 Webhook |
| GET | `/docs` | Swagger UI 文档 |
| GET | `/redoc` | Redoc 文档 |

## Webhook 使用

### 支持的事件类型

| 事件 | 说明 |
|------|------|
| `key.imported` | 密钥导入完成 |
| `key.checked` | 密钥验证完成 |
| `key.tested` | 密钥测试完成 |
| `key.deleted` | 密钥删除 |
| `batch.check.completed` | 批量验证完成 |
| `batch.test.completed` | 批量测试完成 |
| `error.occurred` | 发生错误 |

### 配置 Webhook

```yaml
webhooks:
  - url: "https://example.com/webhook"
    events:
      - "key.imported"
      - "key.checked"
    secret: "your-webhook-secret"  # HMAC-SHA256 签名
    active: true
    max_retries: 3
```

### 签名验证

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

## 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_security.py -v
python -m pytest tests/test_detector.py -v

# 运行测试并查看覆盖率
python -m pytest tests/ --cov=key_manager --cov-report=term-missing
```

### 测试覆盖

| 模块 | 测试文件 | 测试数 |
|------|---------|--------|
| 提供商检测 | `test_detector.py` | 54 |
| 密钥解析 | `test_parser.py` | 12 |
| 验证器 | `test_validator.py` | 5 |
| 检查器 | `test_checker.py` | 4 |
| 提供商合约 | `test_providers.py` | 30 |
| 安全回归 | `test_security.py` | 12 |
| 加密存储 | `test_storage.py` | 26 |
| 错误系统 | `test_errors.py` | 28 |
| 国际化 | `test_i18n.py` | 37 |
| 端到端 | `test_e2e.py` | 17 |
| Webhook | `test_webhook.py` | 35 |
| OpenAPI | `test_openapi.py` | 26 |

## SDK 使用

### Python SDK

```bash
cd sdk/python
pip install -e .
```

```python
from key_manager_sdk import KeyManagerClient

client = KeyManagerClient(base_url="http://localhost:18001")

# 获取密钥列表
keys = client.get_keys()

# 验证单个密钥
result = client.check_single_key(key="sk-xxx", provider="openai")
```

### TypeScript SDK

```bash
cd sdk/typescript
npm install
```

```typescript
import { KeyManagerClient } from 'key-manager-sdk';

const client = new KeyManagerClient({ baseUrl: 'http://localhost:18001' });

// 获取密钥列表
const keys = await client.getKeys();

// 验证单个密钥
const result = await client.checkSingleKey({ key: 'sk-xxx', provider: 'openai' });
```

## 依赖

- Python 3.10+
- httpx - 异步 HTTP 客户端
- FastAPI - Web 框架
- uvicorn - ASGI 服务器
- PyYAML - 配置解析
- Rich - 终端美化
- cryptography - 加密存储
- pydantic - 数据验证

## 已知问题和限制

### 1. 中转站服务商误识别

由于某些中转站服务商（如 Z.AI、DMXAPI、OCoolAI 等）使用与原厂相同的 API 端点和模型，当密钥无效时，错误响应可能包含原厂的签名关键词，导致误识别。

例如：一个硅基流动的密钥，如果被发送到阿里百炼的端点，阿里百炼会返回包含 "model-studio" 和 "apikey-error" 的错误响应，这可能导致系统误认为该密钥是阿里百炼的。

**解决方案**：系统要求至少2个签名匹配（200分）才返回识别结果，以减少误报。

### 2. 签名匹配的局限性

签名匹配依赖于服务商返回的错误响应体中的关键词。如果服务商更改了错误消息格式，签名可能失效。

**建议**：定期运行 `verify_signatures.py` 脚本验证签名的有效性。

### 3. 并发检测的超时问题

全并发探测时，某些服务商可能响应较慢（超过10秒超时）。这可能导致有效的服务商被跳过。

**解决方案**：系统会对失败的模型进行串行重试（最多2次）。

### 4. 智谱/Z.AI 密钥的双重检测

智谱和 Z.AI 使用相同的 GLM 模型和 API 格式，但使用不同的 Base URL：

- 智谱：`https://open.bigmodel.cn/api/paas/v4`
- Z.AI：`https://api.z.ai/api/paas/v4`

同一个密钥可能在两个平台都能工作，系统会返回第一个响应200的服务商。

### 5. 模型列表的时效性

模型列表从 Cherry Studio 同步，每日更新一次。新发布的模型可能需要等待同步后才能被检测到。

## 许可证

MIT License

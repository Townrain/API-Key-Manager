# API Key Manager v2.1.0

**首次正式发布** — 批量管理 45+ AI 服务商 API 密钥的 Python 工具

---

## 🚀 核心功能

### 密钥管理
- **批量导入** — 从 JSON 文件、目录或直接批量输入导入 API 密钥，自动去重
- **密钥验证** — 并发验证 45+ AI 服务商的密钥有效性
- **能力测试** — Token 上限和并发能力测试，支持阶梯式探测
- **模型筛选** — 按类型筛选模型：推理、视觉、联网、免费、嵌入、重排、工具

### 智能提供商检测
- **四级检测策略**：
  1. 前缀匹配 (`sk-proj-` → OpenAI, `AIza` → Google)
  2. 格式匹配 (智谱 `{id}.{secret}` 格式)
  3. 全并发探测 (45+ 服务商 × 5 模型 = 200+ 并发请求)
  4. 错误签名匹配 (通过响应体识别，需至少 2 个签名匹配)

### 双界面
- **CLI** — 命令行工具 (`import`, `check`, `test`, `list`, `report`)
- **Web UI** — 赛博朋克风格管理界面 (端口 18001)
- **REST API** — Swagger UI + Redoc 自动文档

---

## 🔒 安全特性

- **AES-256-GCM 加密存储** — 随机盐值，PBKDF2 密钥派生 (100,000 次迭代)
- **SSRF 防护** — 阻止私有 IP，域名白名单验证
- **路径遍历防护** — 导入端点路径验证
- **时序安全认证** — `hmac.compare_digest()` 防止时序攻击
- **API 认证** — 可选 Bearer Token 认证
- **速率限制** — 每 IP 每分钟 60 请求 (可配置)
- **密钥掩码** — API 响应只返回 `key_masked`

---

## 📦 SDK

### Python SDK
```bash
pip install api-key-manager-sdk
```

```python
from key_manager_sdk import KeyManagerClient

with KeyManagerClient(base_url="http://localhost:18001") as client:
    keys = client.keys(provider="openai", status="valid")
    result = client.check_single(key="sk-xxx")
```

- 同步客户端 `KeyManagerClient`
- 异步客户端 `AsyncKeyManagerClient`
- 自动重试 (指数退避，最多 3 次)
- 完整的异常层次结构

### TypeScript SDK
```bash
npm install @api-key-manager/sdk
```

```typescript
import { KeyManagerClient } from "@api-key-manager/sdk";

const client = new KeyManagerClient({ baseUrl: "http://localhost:18001" });
const keys = await client.keys("openai", "valid");
```

---

## 🌐 支持的 AI 服务商 (45+)

### 国际
OpenAI, Anthropic, Google Gemini, DeepSeek, Groq, Mistral, Cohere, Perplexity, Together AI, Replicate, Hugging Face, Fireworks, OpenRouter, Grok (xAI), Cerebras, NVIDIA, Hyperbolic, Poe

### 中国
阿里百炼 (DashScope), 魔搭 (ModelScope), 智谱 (Zhipu), 月之暗面 (Kimi), MiniMax, 硅基流动 (SiliconFlow), 百川 (Baichuan), 零一万物 (Yi), 阶跃星辰 (StepFun), 豆包 (Doubao), 无问芯穹 (Infini), 小米 (MiMo), 腾讯混元, 中算云 (CSTCloud)

### 新增
LongCat, AI302, PPIO, DMXAPI, OCoolAI, ZAI

### 计划版/编程版
MiMo Plan, MiniMax Plan, DashScope Coding, Zhipu Coding, Kimi Coding, Infini Coding

---

## 🔧 配置

```yaml
# config.yaml
proxy: ""  # HTTP/SOCKS5 代理

check:
  concurrency: 100
  timeout_seconds: 30

auth:
  api_key: "your-secret-key"  # API 认证

rate_limit:
  requests_per_minute: 60
```

环境变量：
- `KEY_MANAGER_SECRET` — 加密密钥
- `KEY_MANAGER_API_KEY` — API 认证密钥

---

## 📊 API 端点 (25+)

| 类别 | 端点 |
|------|------|
| 密钥管理 | `POST /api/import`, `GET /api/keys`, `GET /api/keys/export` |
| 验证 | `POST /api/check/single`, `POST /api/check/batch` |
| 测试 | `POST /api/test/single`, `POST /api/test/token`, `POST /api/test/concurrency` |
| 余额 | `POST /api/balance` |
| 模型 | `GET /api/models`, `POST /api/models/check` (SSE) |
| 提供商 | `GET /api/providers` |
| 统计 | `GET /api/stats`, `GET /api/stats/chart` |
| 日志 | `GET /api/logs`, `GET /api/logs/operations` |
| Webhook | `POST /api/webhooks`, `GET /api/webhooks` |

---

## 🧪 测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行测试并查看覆盖率
python -m pytest tests/ --cov=key_manager --cov-report=term-missing
```

测试覆盖：14 个测试文件，300+ 测试用例

---

## 🛠️ 技术栈

- **语言**: Python 3.10+
- **Web 框架**: FastAPI + Uvicorn
- **HTTP 客户端**: httpx (异步)
- **存储**: AES-256-GCM 加密 JSON
- **配置**: YAML (PyYAML)
- **测试**: pytest + pytest-asyncio
- **代码检查**: ruff

---

## 📥 安装

```bash
# 克隆仓库
git clone https://github.com/Townrain/API-Key-Manager.git
cd API-Key-Manager

# 安装依赖
pip install -r requirements.txt

# 启动 Web 服务
python web.py

# 或使用 CLI
python main.py --help
```

---

## 📝 更新日志

### v2.1.0 (2026-06-04)

#### 新增
- **SDK 重试策略** — 同步和异步 SDK 客户端支持瞬态故障重试 (502, 503, 504, 429, 连接错误)
- **py.typed 标记** — PEP 561 类型检查器兼容性
- **速率限制** — 每 IP 速率限制中间件 (默认 60 请求/分钟)
- **CI/CD 流水线** — GitHub Actions 在 Python 3.10/3.11/3.12 上运行 pytest

#### 修复
- **custom_base_url 接线** — 正确应用 ContextVar
- **Anthropic 端点自动检测** — 兼容端点自动切换头部
- **智能提供商检测** — 使用 `detect_provider()` 替代 `detect_by_prefix()`

### v2.0.0 (2026-06-03)

#### 新增
- **Web API 认证** — 可选 Bearer Token 认证
- **异步 Python SDK** — `AsyncKeyManagerClient`
- **Changelog** — 本文件

---

## 📄 许可证

MIT License

---

## 🔗 链接

- [GitHub 仓库](https://github.com/Townrain/API-Key-Manager)
- [API 文档](http://localhost:18001/docs)
- [Redoc 文档](http://localhost:18001/redoc)

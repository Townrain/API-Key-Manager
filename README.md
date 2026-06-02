# API Key Manager

批量管理 37+ AI 服务商 API 密钥的 Python 工具，支持 CLI 和 Web 两种界面。

## 功能特性

- **批量导入** - 从 JSON 文件导入 API 密钥，自动去重
- **密钥验证** - 并发验证密钥有效性，支持 37+ AI 服务商
- **能力测试** - 测试 Token 上限和并发能力
- **模型筛选** - 按类型筛选模型（推理/视觉/联网/免费/嵌入/重排/工具）
- **提供商自动检测** - 根据 Key 前缀自动识别服务商
- **Web 界面** - 赛博朋克风格的管理界面
- **代理支持** - 支持 HTTP/SOCKS 代理
- **模型能力同步** - 每日从 Cherry Studio 同步 2619 个模型的能力数据

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

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/Townrain/API-Key-Manager.git
cd key

# 安装依赖
pip install -r requirements.txt
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

# 访问 http://localhost:18001
```

## 项目结构

```
key/
├── .github/
│   └── workflows/
│       └── sync-cherry-models.yml   # GitHub Actions 同步模型数据
├── data/
│   ├── input/                       # 导入的 JSON 文件
│   ├── cache/                       # 缓存目录
│   ├── model_capabilities.json      # 模型能力配置（自动生成，2619个模型）
│   └── model_capabilities_fallback.json  # 兜底配置
├── scripts/
│   ├── extract_model_caps.py        # 提取模型能力脚本
│   ├── extract_models.py            # 提取模型列表脚本
│   └── validate_caps.py             # 验证脚本
├── src/
│   ├── providers/                   # AI 服务商实现
│   │   ├── base.py                  # 基类
│   │   ├── __init__.py              # 注册表（37个提供商）
│   │   ├── models_registry.py       # 静态模型列表（自动生成，2619个模型）
│   │   └── ...                      # 具体提供商实现
│   ├── config.py                    # 配置加载
│   ├── parser.py                    # JSON 导入
│   ├── detector.py                  # 提供商检测
│   ├── validator.py                 # 密钥验证
│   ├── checker.py                   # 重试逻辑
│   ├── tester.py                    # 能力测试
│   ├── logger.py                    # 日志
│   ├── proxy.py                     # 代理检测
│   └── model_capabilities.py        # 模型能力检测
├── templates/
│   └── index.html                   # Web 界面（赛博朋克风格）
├── config.yaml.example              # 配置文件示例
├── main.py                          # CLI 入口
├── web.py                           # Web 入口（FastAPI）
└── requirements.txt                 # 依赖
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
  token_steps:                  # Token 测试步长
    - 1024
    - 4096
    - 16384
    - 65536
  concurrency_steps:            # 并发测试步长
    - 1
    - 5
    - 10
    - 20
```

## 模型管理

### 数据统计

| 类别 | 数量 |
|------|------|
| 视觉模型 | 760 |
| 工具调用模型 | 1269 |
| 推理模型 | 698 |
| 联网模型 | 343 |
| 嵌入模型 | 96 |
| **总提供商** | 115 |
| **总模型数** | 2619 |

数据来源：[Cherry Studio](https://github.com/CherryHQ/cherry-studio) 的 `packages/provider-registry/data/models.json`

### 获取模型 vs 检测可用

| 功能 | 说明 | 速度 |
|------|------|------|
| **获取模型** | 从 API 或硬编码列表获取模型列表 | 快（1次API调用） |
| **检测可用** | 逐个检测模型是否真正可用 | 慢（N次API调用）

### 检测可用功能

- **并行检测**：初始使用 5 并发并行检测，提高速度
- **限流降级**：被限流后自动切换到串行模式（1秒延迟）
- **超时处理**：单个模型 15 秒超时，超时后跳过继续检测
- **终止检测**：再次点击按钮可终止当前检测
- **状态显示**：
  - 🟢 绿色：可用模型
  - 🔴 红色：超时模型
  - 🟣 品红色：检测失败模型
  - 🟡 琥珀色：被限流模型

### 检测流程

```
开始检测
    │
    ├─ 并行模式（5并发）
    │     │
    │     ├─ 被限流 → 切换串行模式（1秒延迟）
    │     │
    │     └─ 继续检测
    │
    ├─ 单个模型超时（15秒）→ 标记超时，继续下一个
    │
    └─ 完成 → 显示统计结果
```

### 示例输出

```
可用模型 (57/64)
检测完成, 2 超时 (串行模式)

可用模型:
┌─────────────────────────────────────────┐
│ gpt-4o  gpt-4o-mini  ... (绿色)        │
└─────────────────────────────────────────┘

超时模型:
┌─────────────────────────────────────────┐
│ model1  model2  ... (红色)              │
└─────────────────────────────────────────┘

检测失败:
┌─────────────────────────────────────────┐
│ model3  model4  ... (品红色)            │
└─────────────────────────────────────────┘

被限流:
┌─────────────────────────────────────────┐
│ model5  model6  ... (琥珀色)            │
└─────────────────────────────────────────┘
```

### 自动同步

模型能力配置通过 GitHub Actions 每天从 [Cherry Studio](https://github.com/CherryHQ/cherry-studio) 自动同步。

工作流文件：`.github/workflows/sync-cherry-models.yml`

**数据源**：
- `packages/provider-registry/data/models.json` — 模型能力数据

**同步内容**：
- **模型能力**：vision (760), tooluse (1269), reasoning (698), websearch (343), embedding (96)
- **模型列表**：115 个提供商的 2619 个模型（无 key 时使用）

### 手动同步

```bash
# 克隆 Cherry Studio（只拉取模型数据）
git clone --depth 1 --sparse https://github.com/CherryHQ/cherry-studio.git cherry-studio
cd cherry-studio
git sparse-checkout set packages/provider-registry/data

# 提取模型能力
cd ..
export CHERRY_DATA_DIR="cherry-studio/packages/provider-registry/data"
python scripts/extract_model_caps.py

# 提取模型列表
python scripts/extract_models.py

# 验证
python scripts/validate_caps.py
```

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/keys` | 获取密钥列表 |
| POST | `/api/import` | 导入密钥 |
| POST | `/api/import/upload` | 上传 JSON 文件导入 |
| POST | `/api/check/single` | 验证单个密钥 |
| POST | `/api/check/batch` | 批量验证 |
| POST | `/api/test/single` | 测试单个密钥 |
| POST | `/api/test/token` | 测试 Token 上限 |
| POST | `/api/test/token/batch` | 批量测试 Token |
| POST | `/api/test/concurrency` | 测试并发能力 |
| POST | `/api/test/concurrency/batch` | 批量测试并发 |
| GET | `/api/models` | 获取模型列表（支持 type 筛选） |
| POST | `/api/models/check` | 检测可用模型（SSE 流） |
| GET | `/api/providers` | 获取服务商列表 |
| GET | `/api/providers/detail` | 获取服务商详情 |
| GET | `/api/stats` | 获取统计信息 |
| GET | `/api/stats/chart` | 获取图表数据 |
| GET | `/api/logs` | 获取日志 |
| GET | `/api/logs/operations` | 获取操作日志 |

### 获取模型

```bash
# 获取所有模型（需要 key）
curl "http://localhost:18001/api/models?provider=openai&key=sk-xxx"

# 获取视觉模型
curl "http://localhost:18001/api/models?provider=openai&key=sk-xxx&type=vision"

# 无 key 时使用静态列表
curl "http://localhost:18001/api/models?provider=openai"
```

响应：
```json
{
    "provider": "openai",
    "models": ["gpt-4o", "gpt-4o-mini", ...],
    "total": 10,
    "type_filter": "all",
    "source": "api"  // 或 "static"
}
```

### 检测可用模型

```bash
# 检测所有模型
curl -X POST "http://localhost:18001/api/models/check" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-xxx", "provider": "openai"}'

# 只检测推理模型
curl -X POST "http://localhost:18001/api/models/check" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-xxx", "provider": "openai", "type": "reasoning"}'
```

响应（SSE 流）：
```
data: {"type": "progress", "current": 1, "total": 10, "model": "gpt-4o", "mode": "parallel"}
data: {"type": "result", "model": "gpt-4o", "available": true, "status": "ok"}
data: {"type": "progress", "current": 2, "total": 10, "model": "gpt-4o-mini", "mode": "parallel"}
data: {"type": "result", "model": "gpt-4o-mini", "available": false, "status": "error"}
data: {"type": "complete", "total": 10, "available": 8, "timeout": 1, "mode": "parallel"}
```

### 模型状态

| 状态 | 说明 |
|------|------|
| `ok` | 可用（200 响应） |
| `error` | 检测失败（非 200 响应） |
| `timeout` | 超时（15 秒无响应） |
| `rate_limited` | 被限流（429 响应） |

## 数据存储

所有数据以 JSON 文件形式存储在 `data/` 目录：

- `keys.json` - 密钥主存储
- `check_results.json` - 验证结果
- `test_results.json` - 测试结果
- `logs/` - 日志文件

密钥在存储和显示时始终使用掩码格式：`{前6位}...{后4位}`

## 依赖

- Python 3.10+
- httpx - 异步 HTTP 客户端
- FastAPI - Web 框架
- uvicorn - ASGI 服务器
- PyYAML - 配置解析
- Rich - 终端美化

## 许可证

MIT License

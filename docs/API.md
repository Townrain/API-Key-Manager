# API Key Manager - API Documentation

## Base URL

```
http://localhost:18001
```

## Authentication

Currently, the API does not require authentication. For production use, consider adding an API gateway or reverse proxy with authentication.

## Response Format

All API responses use JSON format.

### Success Response

```json
{
  "key": "value",
  ...
}
```

### Error Response

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Error description",
    "details": {}
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_MISSING_KEY` | 400 | No key provided |
| `VALIDATION_INVALID_FORMAT` | 400 | Invalid key format |
| `VALIDATION_PROVIDER_UNKNOWN` | 400 | Cannot detect provider |
| `VALIDATION_FILE_NOT_FOUND` | 400 | File not found |
| `VALIDATION_FILE_FORMAT` | 400 | Invalid file format |
| `STORAGE_READ_ERROR` | 500 | Failed to read storage |
| `STORAGE_WRITE_ERROR` | 500 | Failed to write storage |
| `STORAGE_ENCRYPTION_ERROR` | 500 | Encryption/decryption failed |
| `STORAGE_MIGRATION_ERROR` | 500 | Data migration failed |
| `PROVIDER_CHECK_FAILED` | 502 | Provider check failed |
| `PROVIDER_NOT_SUPPORTED` | 400 | Provider not supported |
| `PROVIDER_RATE_LIMITED` | 429 | Rate limited by provider |
| `SYSTEM_INTERNAL_ERROR` | 500 | Internal server error |
| `SYSTEM_PROGRESS_CONFLICT` | 409 | Another operation in progress |

---

## Endpoints

### Keys

#### Get Keys

Get list of API keys with pagination and filtering.

```
GET /api/keys
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | string | - | Filter by provider name |
| `status` | string | - | Filter by status (valid/invalid/error/unknown) |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 50 | Items per page |

**Response:**

```json
{
  "keys": [
    {
      "key": "sk-abc123def456",
      "key_masked": "sk-abc...456",
      "provider": "openai",
      "status": "valid",
      "last_checked": "2024-01-01T00:00:00Z",
      "last_error": null,
      "error_type": null,
      "tests": {
        "max_tokens": 16384,
        "max_concurrency": 10
      },
      "models": ["gpt-4o", "gpt-4o-mini"],
      "sources_count": 1,
      "balance": {
        "balance": 100.0,
        "currency": "USD"
      }
    }
  ],
  "total": 100,
  "page": 1,
  "total_pages": 2,
  "page_size": 50
}
```

**Example:**

```bash
curl "http://localhost:18001/api/keys?provider=openai&status=valid&page=1"
```

---

#### Export Valid Keys

Export all valid keys for use in other applications.

```
GET /api/keys/export
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `provider` | string | - | Filter by provider name |

**Response:**

```json
{
  "keys": [
    {
      "key": "sk-abc123def456",
      "provider": "openai",
      "max_tokens": 16384,
      "max_concurrency": 10
    }
  ],
  "total": 50
}
```

**Example:**

```bash
curl "http://localhost:18001/api/keys/export?provider=anthropic"
```

---

#### Clear Keys

Delete all imported keys.

```
POST /api/keys/clear
```

**Response:**

```json
{
  "cleared": 100
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/keys/clear
```

---

### Import

#### Import Keys

Import keys from a file or directory.

```
POST /api/import
```

**Request Body:**

```json
{
  "file": "./data/input/keys.json",
  "directory": "./data/input",
  "batch": "batch-2024-01"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | string | No* | Path to JSON file |
| `directory` | string | No* | Directory to scan |
| `batch` | string | No | Batch label |

*Either `file` or `directory` is required.

**Response:**

```json
{
  "new": 10,
  "duplicates": 2,
  "errors": []
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/import \
  -H "Content-Type: application/json" \
  -d '{"file": "./data/input/example.json", "batch": "test-batch"}'
```

---

#### Upload JSON File

Upload a JSON file to import keys.

```
POST /api/import/upload
```

**Request:** `multipart/form-data`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file` | file | Yes | JSON file to upload |

**Response:**

```json
{
  "new": 5,
  "duplicates": 1,
  "errors": [],
  "filename": "keys.json"
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/import/upload \
  -F "file=@keys.json"
```

---

### Check

#### Check Single Key

Validate a single API key by making a test request.

```
POST /api/check/single
```

**Request Body:**

```json
{
  "key": "sk-abc123def456",
  "provider": "openai",
  "custom_base_url": "https://api.openai.com/v1"
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `key` | string | Yes | API key to check |
| `provider` | string | No | Provider name (auto-detected if omitted) |
| `custom_base_url` | string | No | Custom API base URL |

**Response:**

```json
{
  "key": "sk-abc123def456",
  "key_masked": "sk-abc...456",
  "provider": "openai",
  "display_name": "OpenAI",
  "status": "valid",
  "status_code": 200,
  "latency_ms": 150.5,
  "error": null,
  "error_type": null,
  "balance": null,
  "models": []
}
```

**Status Values:**

| Status | Description |
|--------|-------------|
| `valid` | Key is valid and working |
| `invalid` | Key is invalid (401/403) |
| `error` | Check failed due to network/server error |

**Example:**

```bash
curl -X POST http://localhost:18001/api/check/single \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-abc123", "provider": "openai"}'
```

---

#### Check Batch

Check multiple keys at once (without persisting to storage).

```
POST /api/check/batch
```

**Request Body:**

```json
{
  "keys": [
    {"key": "sk-abc123", "provider": "openai"},
    {"key": "sk-def456", "provider": "anthropic"}
  ],
  "timeout": 10,
  "concurrency": 50,
  "custom_base_url": null
}
```

**Response:**

```json
{
  "results": [
    {
      "key_masked": "sk-abc...123",
      "provider": "openai",
      "status": "valid",
      "status_code": 200,
      "latency_ms": 120,
      "error": null,
      "error_type": null,
      "balance": null
    }
  ],
  "summary": {
    "total": 2,
    "valid": 1,
    "invalid": 0,
    "error": 1
  }
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/check/batch \
  -H "Content-Type: application/json" \
  -d '{
    "keys": [
      {"key": "sk-abc123", "provider": "openai"},
      {"key": "sk-def456", "provider": "anthropic"}
    ]
  }'
```

---

### Balance

#### Check Balance

Query the balance/credits for a single key.

```
POST /api/balance
```

**Request Body:**

```json
{
  "key": "sk-abc123def456",
  "provider": "openai",
  "custom_base_url": null
}
```

**Response:**

```json
{
  "provider": "openai",
  "supported": true,
  "balance": 100.0,
  "currency": "USD",
  "key_masked": "sk-abc...456"
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/balance \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-abc123", "provider": "openai"}'
```

---

### Test

#### Test Single Key

Test token limits and concurrency for a single key.

```
POST /api/test/single
```

**Request Body:**

```json
{
  "key": "sk-abc123def456",
  "provider": "openai"
}
```

**Response:**

```json
{
  "provider": "openai",
  "key_masked": "sk-abc...456",
  "max_tokens": 16384,
  "max_concurrency": 10,
  "models": ["gpt-4o", "gpt-4o-mini"]
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/test/single \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-abc123", "provider": "openai"}'
```

---

#### Test Token Per Model

Test token limits for each available model.

```
POST /api/test/token
```

**Request Body:**

```json
{
  "key": "sk-abc123def456",
  "provider": "openai"
}
```

**Response:**

```json
{
  "provider": "openai",
  "key_masked": "sk-abc...456",
  "total_models": 5,
  "tested_models": 5,
  "results": [
    {
      "model": "gpt-4o",
      "max_tokens": 16384,
      "success": true,
      "error": null
    }
  ]
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/test/token \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-abc123", "provider": "openai"}'
```

---

#### Test Concurrency Per Model

Test concurrency limits for each available model.

```
POST /api/test/concurrency
```

**Request Body:**

```json
{
  "key": "sk-abc123def456",
  "provider": "openai",
  "concurrency": 10
}
```

**Response:**

```json
{
  "provider": "openai",
  "key_masked": "sk-abc...456",
  "total_models": 5,
  "tested_models": 5,
  "results": [
    {
      "model": "gpt-4o",
      "max_concurrency": 10
    }
  ]
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/test/concurrency \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-abc123", "provider": "openai", "concurrency": 10}'
```

---

### Models

#### Get Models

Get available models for a provider.

```
GET /api/models
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | No* | Provider name |
| `key` | string | No* | API key (for auto-detection) |
| `type` | string | No | Filter by type (vision/tooluse/embedding/rerank/reasoning/websearch/free/all) |

*Either `provider` or `key` is required.

**Response:**

```json
{
  "provider": "openai",
  "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
  "total": 3,
  "type_filter": "all",
  "source": "api"
}
```

**Model Types:**

| Type | Description |
|------|-------------|
| `vision` | Vision/multimodal models |
| `tooluse` | Tool/function calling models |
| `embedding` | Embedding models |
| `rerank` | Reranking models |
| `reasoning` | Reasoning models (o1, o3, etc.) |
| `websearch` | Web search models |
| `free` | Free tier models |
| `all` | All models (default) |

**Example:**

```bash
curl "http://localhost:18001/api/models?provider=openai&type=vision"
```

---

#### Check Available Models

Check which models are actually available by making test requests.

```
POST /api/models/check
```

**Request Body:**

```json
{
  "key": "sk-abc123def456",
  "provider": "openai",
  "type": "all"
}
```

**Response (SSE Stream):**

```
data: {"type": "progress", "current": 0, "total": 10, "model": "starting", "concurrency": 5}
data: {"type": "result", "model": "gpt-4o", "available": true, "status": "ok"}
data: {"type": "result", "model": "gpt-4o-mini", "available": true, "status": "ok"}
data: {"type": "complete", "total": 10, "available": 8, "timeout": 1}
```

**Example:**

```bash
curl -X POST "http://localhost:18001/api/models/check" \
  -H "Content-Type: application/json" \
  -d '{"key": "sk-abc123", "provider": "openai", "type": "reasoning"}'
```

---

### Providers

#### Get Providers

Get list of all supported providers.

```
GET /api/providers
```

**Response:**

```json
{
  "providers": [
    {
      "name": "openai",
      "display_name": "OpenAI",
      "prefix": "sk-proj-",
      "base_url": "https://api.openai.com/v1",
      "type": "ai"
    }
  ],
  "total": 45
}
```

**Example:**

```bash
curl http://localhost:18001/api/providers
```

---

#### Get Provider Detail

Get detailed information about a specific provider.

```
GET /api/providers/detail
```

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `provider` | string | No | Provider name (returns all if omitted) |

**Response:**

```json
{
  "name": "openai",
  "display_name": "OpenAI",
  "prefix": "sk-proj-",
  "base_url": "https://api.openai.com/v1",
  "website_url": "https://platform.openai.com",
  "docs_url": "https://platform.openai.com/docs",
  "website_name": "OpenAI"
}
```

**Example:**

```bash
curl "http://localhost:18001/api/providers/detail?provider=anthropic"
```

---

### Stats

#### Get Statistics

Get overall statistics about keys.

```
GET /api/stats
```

**Response:**

```json
{
  "providers": {
    "openai": {
      "total": 50,
      "valid": 45,
      "invalid": 3,
      "error": 2,
      "display_name": "OpenAI"
    }
  },
  "total": 100
}
```

**Example:**

```bash
curl http://localhost:18001/api/stats
```

---

#### Get Chart Data

Get statistics formatted for charts.

```
GET /api/stats/chart
```

**Response:**

```json
{
  "providers": {
    "openai": {"total": 50, "valid": 45, "invalid": 3, "error": 2}
  },
  "statuses": {"valid": 80, "invalid": 10, "error": 5, "unknown": 5}
}
```

**Example:**

```bash
curl http://localhost:18001/api/stats/chart
```

---

### Logs

#### Get Logs

Get recent log entries.

```
GET /api/logs
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lines` | integer | 100 | Number of log lines to return |

**Response:**

```json
{
  "logs": ["2024-01-01 00:00:00 - INFO - ..."],
  "total": 100
}
```

**Example:**

```bash
curl "http://localhost:18001/api/logs?lines=50"
```

---

#### Get Operations

Get structured operations log.

```
GET /api/logs/operations
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of operations to return |

**Response:**

```json
{
  "operations": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "action": "check",
      "provider": "openai",
      "key_masked": "sk-abc...456",
      "status": "valid",
      "details": "..."
    }
  ],
  "total": 50
}
```

**Example:**

```bash
curl "http://localhost:18001/api/logs/operations?limit=20"
```

---

### Webhooks

#### List Webhooks

Get all registered webhooks.

```
GET /api/webhooks
```

**Response:**

```json
{
  "webhooks": [
    {
      "id": "a1b2c3d4",
      "url": "https://example.com/webhook",
      "events": ["key.imported", "key.checked"],
      "active": true,
      "max_retries": 3,
      "has_secret": true
    }
  ],
  "total": 1
}
```

**Example:**

```bash
curl http://localhost:18001/api/webhooks
```

---

#### Create Webhook

Register a new webhook.

```
POST /api/webhooks
```

**Request Body:**

```json
{
  "url": "https://example.com/webhook",
  "events": ["key.imported", "key.checked", "key.tested"],
  "secret": "my-webhook-secret",
  "active": true,
  "max_retries": 3
}
```

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `url` | string | Yes | Webhook URL to receive notifications |
| `events` | array | No | Event types to subscribe (all if omitted) |
| `secret` | string | No | Secret for HMAC-SHA256 signature |
| `active` | boolean | No | Enable/disable webhook (default: true) |
| `max_retries` | integer | No | Max retry attempts (default: 3) |

**Events:**

| Event | Description |
|-------|-------------|
| `key.imported` | Keys imported |
| `key.checked` | Key checked |
| `key.tested` | Key tested |
| `key.deleted` | Keys deleted |
| `batch.check.completed` | Batch check completed |
| `batch.test.completed` | Batch test completed |
| `error.occurred` | Error occurred |

**Response:**

```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/webhook",
  "message": "Webhook registered successfully"
}
```

**Example:**

```bash
curl -X POST http://localhost:18001/api/webhooks \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/webhook",
    "events": ["key.imported", "key.checked"],
    "secret": "my-secret"
  }'
```

---

#### Get Webhook

Get webhook details.

```
GET /api/webhooks/{webhook_id}
```

**Response:**

```json
{
  "id": "a1b2c3d4",
  "url": "https://example.com/webhook",
  "events": ["key.imported", "key.checked"],
  "active": true,
  "max_retries": 3,
  "has_secret": true
}
```

**Example:**

```bash
curl http://localhost:18001/api/webhooks/a1b2c3d4
```

---

#### Update Webhook

Update webhook configuration.

```
PUT /api/webhooks/{webhook_id}
```

**Request Body:**

```json
{
  "active": false,
  "max_retries": 5
}
```

**Response:**

```json
{
  "message": "Webhook updated successfully"
}
```

**Example:**

```bash
curl -X PUT http://localhost:18001/api/webhooks/a1b2c3d4 \
  -H "Content-Type: application/json" \
  -d '{"active": false}'
```

---

#### Delete Webhook

Delete a webhook.

```
DELETE /api/webhooks/{webhook_id}
```

**Response:**

```json
{
  "message": "Webhook deleted successfully"
}
```

**Example:**

```bash
curl -X DELETE http://localhost:18001/api/webhooks/a1b2c3d4
```

---

#### Get Delivery Log

Get webhook delivery history.

```
GET /api/webhooks/log/deliveries
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of entries to return |

**Response:**

```json
{
  "deliveries": [
    {
      "url": "https://example.com/webhook",
      "event": "key.checked",
      "success": true,
      "status_code": 200,
      "attempts": 1,
      "error": null,
      "delivered_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 50
}
```

**Example:**

```bash
curl "http://localhost:18001/api/webhooks/log/deliveries?limit=20"
```

---

#### Clear Delivery Log

Clear webhook delivery history.

```
DELETE /api/webhooks/log/deliveries
```

**Response:**

```json
{
  "message": "Delivery log cleared"
}
```

**Example:**

```bash
curl -X DELETE http://localhost:18001/api/webhooks/log/deliveries
```

---

### Progress

#### Get Progress

Get current operation progress.

```
GET /api/progress
```

**Response:**

```json
{
  "active": true,
  "current": 50,
  "total": 100,
  "status": "loading",
  "results": null
}
```

**Example:**

```bash
curl http://localhost:18001/api/progress
```

---

#### Stream Progress

Stream progress updates via Server-Sent Events.

```
GET /api/progress/stream
```

**Response (SSE):**

```
data: {"active": true, "current": 50, "total": 100, "status": "loading"}
data: {"active": false, "current": 100, "total": 100, "status": "done"}
```

**Example:**

```bash
curl -N http://localhost:18001/api/progress/stream
```

---

### Webhook Payload

When a webhook is triggered, the following payload is sent:

```json
{
  "event": "key.checked",
  "timestamp": "2024-01-01T00:00:00Z",
  "data": {
    "key_masked": "sk-abc...456",
    "provider": "openai",
    "status": "valid",
    "latency_ms": 150,
    "error": null
  }
}
```

**Headers:**

| Header | Description |
|--------|-------------|
| `Content-Type` | `application/json` |
| `User-Agent` | `API-Key-Manager/1.0` |
| `X-Webhook-Event` | Event type |
| `X-Webhook-Timestamp` | Event timestamp |
| `X-Webhook-Signature` | HMAC-SHA256 signature (if secret configured) |

**Signature Verification:**

```python
import hmac
import hashlib
import json

def verify_signature(payload: dict, secret: str, signature: str) -> bool:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    expected = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return signature == f"sha256={expected}"
```

---

## Internationalization (i18n)

Error messages support Chinese and English based on `Accept-Language` header.

```bash
# English errors
curl -H "Accept-Language: en" http://localhost:18001/api/check/single \
  -H "Content-Type: application/json" \
  -d '{}'

# Chinese errors (default)
curl http://localhost:18001/api/check/single \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## API Documentation UI

- **Swagger UI**: http://localhost:18001/docs
- **Redoc**: http://localhost:18001/redoc
- **OpenAPI Spec**: http://localhost:18001/openapi.json

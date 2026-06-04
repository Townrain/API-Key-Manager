# API Key Manager SDK

Manage and validate API keys for 37+ AI providers. Import, check validity, test token limits and concurrency, query balances, and export working keys.

Version: 1.0.0

## Installation

### Python

```bash
pip install key-manager-sdk
```

Or from source:

```bash
pip install ./sdk/python
```

### TypeScript

```bash
npm install @api-key-manager/sdk
```

Or from source:

```bash
cd sdk/typescript && npm install && npm run build
```

## Quick Start

### Python

```python
from key_manager_sdk import KeyManagerClient

client = KeyManagerClient(base_url="http://localhost:8000")

# List keys
keys = client.get_keys(provider="openai", page=1, page_size=10)
print(keys)

# Check a single key
result = client.check_single_key()
print(result)

# Get stats
stats = client.get_stats()
print(stats)

# Close client
client.close()

# Or use context manager
with KeyManagerClient(base_url="http://localhost:8000") as client:
    providers = client.get_providers()
```

### TypeScript

```typescript
import { KeyManagerClient } from "@api-key-manager/sdk";

const client = new KeyManagerClient({
  baseUrl: "http://localhost:8000",
});

// List keys
const keys = await client.getKeys("openai", undefined, 1, 10);
console.log(keys);

// Get stats
const stats = await client.getStats();
console.log(stats);

// Get providers
const providers = await client.getProviders();
console.log(providers);
```

## Error Handling

### Python

```python
from key_manager_sdk import (
    KeyManagerClient,
    KeyManagerError,
    AuthenticationError,
    NotFoundError,
    ValidationError,
    RateLimitError,
    ServerError,
)

client = KeyManagerClient(base_url="http://localhost:8000")

try:
    result = client.check_single_key()
except AuthenticationError:
    print("Invalid API key")
except NotFoundError:
    print("Resource not found")
except ValidationError as e:
    print(f"Validation errors: {e.errors}")
except RateLimitError as e:
    print(f"Rate limited, retry after {e.retry_after}s")
except ServerError:
    print("Server error")
except KeyManagerError as e:
    print(f"API error: {e}")
```

### TypeScript

```typescript
import {
  KeyManagerClient,
  KeyManagerError,
  AuthenticationError,
  NotFoundError,
  ValidationErrorResponse,
  RateLimitError,
  ServerError,
} from "@api-key-manager/sdk";

const client = new KeyManagerClient({ baseUrl: "http://localhost:8000" });

try {
  const result = await client.checkSingleKey();
} catch (err) {
  if (err instanceof AuthenticationError) {
    console.error("Invalid API key");
  } else if (err instanceof NotFoundError) {
    console.error("Resource not found");
  } else if (err instanceof ValidationErrorResponse) {
    console.error("Validation errors:", err.errors);
  } else if (err instanceof RateLimitError) {
    console.error(`Rate limited, retry after ${err.retryAfter}s`);
  } else if (err instanceof ServerError) {
    console.error("Server error");
  } else if (err instanceof KeyManagerError) {
    console.error("API error:", err.message);
  }
}
```

## API Reference

| Python Method | TypeScript Method | HTTP | Path | Description |
|---|---|---|---|---|
| `import` / `import` | POST `/api/import` | Api Import |
| `import_upload` / `importUpload` | POST `/api/import/upload` | Api Import Upload |
| `keys` / `keys` | GET `/api/keys` | Api List Keys |
| `keys_export` / `keysExport` | GET `/api/keys/export` | Api Export Keys |
| `keys_clear` / `keysClear` | POST `/api/keys/clear` | Api Clear Keys |
| `check` / `check` | POST `/api/check` | Api Check |
| `check_single` / `checkSingle` | POST `/api/check/single` | Api Check Single |
| `check_batch` / `checkBatch` | POST `/api/check/batch` | Api Check Batch |
| `test` / `test` | POST `/api/test` | Api Test |
| `test_single` / `testSingle` | POST `/api/test/single` | Api Test Single |
| `test_token` / `testToken` | POST `/api/test/token` | Api Test Token |
| `test_concurrency` / `testConcurrency` | POST `/api/test/concurrency` | Api Test Concurrency |
| `balance` / `balance` | POST `/api/balance` | Api Balance |
| `models` / `models` | GET `/api/models` | Api Models |
| `models_check` / `modelsCheck` | POST `/api/models/check` | Api Models Check |
| `providers` / `providers` | GET `/api/providers` | Api Providers |
| `providers_detail` / `providersDetail` | GET `/api/providers/detail` | Api Providers Detail |
| `stats` / `stats` | GET `/api/stats` | Api Stats |
| `stats_chart` / `statsChart` | GET `/api/stats/chart` | Api Stats Chart |
| `progress` / `progress` | GET `/api/progress` | Api Progress |
| `progress_stream` / `progressStream` | GET `/api/progress/stream` | Api Progress Stream |
| `proxy` / `proxy` | GET `/api/proxy` | Api Proxy |
| `logs` / `logs` | GET `/api/logs` | Api Logs |
| `logs_operations` / `logsOperations` | GET `/api/logs/operations` | Api Logs Operations |
| `logs_files` / `logsFiles` | GET `/api/logs/files` | Api Logs Files |
| `signature_report` / `signatureReport` | GET `/api/signature-report` | Api Signature Report |

## Models

Both SDKs export typed models for all API responses:

- `APIKey` — Single API key object
- `KeyListResponse` — Paginated key list
- `CheckResult` — Key validation result
- `BalanceResult` — Balance query result
- `TestResult` — Key test result
- `StatsResponse` — Aggregate statistics
- `ProviderInfo` — Provider metadata
- `ProgressResponse` — Task progress
- `LogEntry` / `OperationLog` — Log entries

## Regenerating SDKs

```bash
python scripts/generate_sdk.py
```

## License

MIT

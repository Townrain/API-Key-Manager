const BASE_URL = 'http://127.0.0.1:18001';

// Auth token — set via setAuthToken()
let _authToken = '';

export function setAuthToken(token: string) {
  _authToken = token;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options?.headers as Record<string, string>,
  };
  if (_authToken) {
    headers['Authorization'] = `Bearer ${_authToken}`;
  }
  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// --- Interfaces ---

export interface ProviderInfo {
  name: string;
  display_name: string;
  prefix?: string;
  base_url?: string;
  type?: string;
}

export interface ProviderDetail {
  name: string;
  display_name: string;
  prefix?: string;
  base_url?: string;
  website_url?: string;
  docs_url?: string;
  website_name?: string;
}

export interface KeyInfo {
  key_masked: string;
  provider: string;
  status: string;
  last_checked?: string | null;
  last_error?: string | null;
  error_type?: string | null;
  tests?: Record<string, any>;
  models?: string[];
  sources_count?: number;
  balance?: number | null;
}

export interface ProviderStat {
  total: number;
  valid: number;
  invalid: number;
  error: number;
  display_name: string;
}

export interface Stats {
  total?: number;
  providers: Record<string, ProviderStat>;
}

export interface CheckResult {
  key_masked: string;
  provider: string;
  display_name?: string;
  status: string;
  status_code?: number;
  latency_ms: number;
  error?: string;
  error_type?: string;
  balance?: Record<string, any> | null;
  models?: string[];
}

export interface CheckBatchResult {
  key_masked: string;
  provider: string;
  status: string;
  status_code?: number;
  latency_ms?: number;
  error?: string;
  error_type?: string;
}

export interface CheckBatchSummary {
  total: number;
  valid: number;
  invalid: number;
  error: number;
}

export interface CheckBatchResponse {
  results: CheckBatchResult[];
  summary: CheckBatchSummary;
}

export interface TestSingleResponse {
  provider: string;
  key_masked: string;
  max_tokens?: number;
  max_concurrency?: number;
  models?: string[];
  error?: string;
}

export interface BalanceResponse {
  provider: string;
  supported: boolean;
  balance?: number;
  currency?: string;
  key_masked?: string;
  error?: string;
}

export interface ModelsResponse {
  provider: string;
  models: string[];
  total: number;
  type_filter: string;
  source?: string;
  hint?: string;
  error?: string;
}

export interface LogEntry {
  timestamp?: string;
  level?: string;
  message: string;
  extra?: Record<string, any> | null;
}

export interface OperationEntry {
  timestamp?: string;
  action: string;
  detail: string;
  extra?: Record<string, any> | null;
}

export interface ProxyStatus {
  proxy?: string;
  source: string;
}

export interface WebhookInfo {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  max_retries: number;
}

export interface KeyExportItem {
  key_masked: string;
  provider: string;
  max_tokens?: number | null;
  max_concurrency?: number | null;
}

export interface KeyExportResponse {
  keys: KeyExportItem[];
  total: number;
}

export interface WebhookDelivery {
  webhook_id?: string;
  event?: string;
  status_code?: number;
  success: boolean;
  timestamp?: string;
  error?: string;
}

export interface ProviderConfig {
  name: string;
  display_name: string;
  base_url: string;
  check_endpoint: string;
  chat_endpoint?: string;
  key_prefixes?: string[];
  error_signatures?: string[];
  website_url?: string;
  docs_url?: string;
  source?: string;
}

export interface ProviderCreateBody {
  name: string;
  base_url: string;
  check_endpoint: string;
  chat_endpoint?: string;
  key_prefixes?: string[];
  error_signatures?: string[];
  website_url?: string;
  docs_url?: string;
}

export interface ProviderTestResult {
  success: boolean;
  provider: string;
  models_count?: number;
  sample_models?: string[];
  error?: string;
}

export interface ModelTestResult {
  provider: string;
  model: string;
  max_tokens?: number;
  max_concurrency?: number;
  error?: string | null;
}

export interface SignatureReportResult {
  provider: string;
  status_code?: number;
  error?: string;
  valid?: boolean;
  response_body?: string;
  unique_signatures: {
    total: number;
    matched: string[];
    missing: string[];
    match_rate: number;
  };
  new_signatures?: string[];
  conflicts?: { signature: string; other_provider: string }[];
}

export interface SignatureReport {
  summary: {
    total_providers: number;
    successful_tests: number;
    full_match: number;
    partial_match: number;
    no_match: number;
    has_conflicts: number;
    has_new_signatures: number;
  };
  results: SignatureReportResult[];
}

// --- API ---

export const api = {
  // Stats
  getStats: () => request<Stats>('/api/stats'),

  // Providers
  getProviders: async () => {
    const res = await request<{ providers: ProviderInfo[]; total: number } | ProviderInfo[]>('/api/providers');
    return Array.isArray(res) ? res : (res.providers || []);
  },
  getProviderDetails: async () => {
    const res = await request<{ providers: ProviderDetail[]; total: number } | ProviderDetail[]>('/api/providers/detail');
    return Array.isArray(res) ? res : (res.providers || []);
  },
  getProvider: (name: string) => request<ProviderConfig>(`/api/providers/${name}`),
  createProvider: (body: ProviderCreateBody) =>
    request<{ success: boolean; provider: ProviderCreateBody }>('/api/providers', { method: 'POST', body: JSON.stringify(body) }),
  updateProvider: (name: string, body: Partial<ProviderCreateBody>) =>
    request<{ success: boolean; provider: Partial<ProviderCreateBody> }>(`/api/providers/${name}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteProvider: (name: string) =>
    request<{ success: boolean }>(`/api/providers/${name}`, { method: 'DELETE' }),
  testProviderConnectivity: (name: string, key?: string) =>
    request<ProviderTestResult>(`/api/providers/${name}/test`, { method: 'POST', body: JSON.stringify({ key: key || '' }) }),

  // Keys
  getKeys: (params?: { provider?: string; status?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams();
    if (params?.provider) q.set('provider', params.provider);
    if (params?.status) q.set('status', params.status);
    if (params?.page) q.set('page', String(params.page));
    if (params?.page_size) q.set('page_size', String(params.page_size));
    return request<{ keys: KeyInfo[]; total: number; page: number; page_size: number }>(`/api/keys?${q}`);
  },
  exportKeys: () => request<KeyExportResponse>('/api/keys/export'),
  clearKeys: () => request<void>('/api/keys/clear', { method: 'POST' }),
  deleteKey: (keyMasked: string) => request<{ deleted: number; key_masked: string }>('/api/keys/delete', { method: 'POST', body: JSON.stringify({ key_masked: keyMasked }) }),
  revealKeyByMasked: (keyMasked: string) => request<{ key: string }>('/api/keys/get-full-key', { method: 'POST', body: JSON.stringify({ key_masked: keyMasked }) }),

  // Check
  checkKey: (key: string, provider?: string) =>
    request<CheckResult>('/api/check/single', { method: 'POST', body: JSON.stringify({ key, provider }) }),
  checkSingle: (key: string, provider?: string, baseUrl?: string, model?: string) =>
    request<CheckResult>('/api/check/single', { method: 'POST', body: JSON.stringify({ key, provider, custom_base_url: baseUrl, model: model || undefined }) }),
  checkBatch: (keys: { key: string }[], baseUrl?: string) =>
    request<CheckBatchResponse>('/api/check/batch', { method: 'POST', body: JSON.stringify({ keys, custom_base_url: baseUrl }) }),
  checkAll: () => request<void>('/api/check', { method: 'POST', body: '{}' }),

  // Test
  testSingle: (key: string, provider?: string) =>
    request<TestSingleResponse>('/api/test/single', { method: 'POST', body: JSON.stringify({ key, provider }) }),
  testToken: (key?: string) =>
    request<void>('/api/test/token', { method: 'POST', body: JSON.stringify({ key }) }),
  testConcurrency: (key?: string) =>
    request<void>('/api/test/concurrency', { method: 'POST', body: JSON.stringify({ key }) }),
  testTokenModel: (key: string, model: string, provider?: string) =>
    request<ModelTestResult>('/api/test/token/model', { method: 'POST', body: JSON.stringify({ key, model, provider }) }),
  testConcurrencyModel: (key: string, model: string, provider?: string, concurrency?: number) =>
    request<ModelTestResult>('/api/test/concurrency/model', { method: 'POST', body: JSON.stringify({ key, model, provider, concurrency }) }),

  // Balance
  queryBalance: (key: string, provider: string, baseUrl?: string) =>
    request<BalanceResponse>('/api/balance', { method: 'POST', body: JSON.stringify({ key, provider, custom_base_url: baseUrl }) }),

  // Models
  getModels: (params?: { provider?: string; type_filter?: string; key?: string }) => {
    const q = new URLSearchParams();
    if (params?.provider) q.set('provider', params.provider);
    if (params?.type_filter) q.set('type_filter', params.type_filter);
    if (params?.key) q.set('key', params.key);
    return request<ModelsResponse>(`/api/models?${q}`);
  },
  getModelCapabilities: async (models: string[]) => {
    const q = new URLSearchParams();
    q.set('models', models.join(','));
    return request<{ capabilities: Record<string, any> }>(`/api/models/capabilities?${q}`);
  },

  // Import
  importSingleKey: (key: string) =>
    request<{ new: number; duplicates: number; errors: string[] }>('/api/import', { method: 'POST', body: JSON.stringify({ batch: [key] }) }),

  importUpload: async (filename: string, data: string) => {
    const formData = new FormData();
    const blob = new Blob([data], { type: 'application/json' });
    formData.append('file', blob, filename);
    const headers: Record<string, string> = {};
    if (_authToken) {
      headers['Authorization'] = `Bearer ${_authToken}`;
    }
    const res = await fetch(`${BASE_URL}/api/import/upload`, { method: 'POST', headers, body: formData });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  },

  // Logs
  getLogs: async () => {
    const res = await request<{ logs?: LogEntry[] } | LogEntry[]>('/api/logs');
    if (Array.isArray(res)) return res;
    return res.logs || [];
  },
  getOperations: async () => {
    const res = await request<{ operations: OperationEntry[]; total: number } | OperationEntry[]>('/api/logs/operations');
    return Array.isArray(res) ? res : (res.operations || []);
  },
  clearLogs: (date?: string) => {
    const q = date ? `?date=${encodeURIComponent(date)}` : '';
    return request<{ success: boolean }>(`/api/logs${q}`, { method: 'DELETE' });
  },

  // Proxy
  getProxy: () => request<ProxyStatus>('/api/proxy'),

  // Signature Report
  getSignatureReport: () => request<SignatureReport>('/api/signature-report'),

  // Test all
  testAll: () => request<void>('/api/test', { method: 'POST', body: '{}' }),

  // Progress
  getProgress: () => request<{ active: boolean; current: number; total: number; status: string }>('/api/progress'),
  progressStream: async (
    onEvent: (event: { type: string; data: any }) => void,
    signal?: AbortSignal,
  ) => {
    const res = await fetch(`${BASE_URL}/api/progress/stream`, { signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const reader = res.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try { onEvent(JSON.parse(line.slice(6))); } catch {}
        }
      }
    }
  },

  // Models Check (SSE)
  checkModelsSSE: async (
    params: { provider?: string; key: string },
    onEvent: (event: { type: string; data: any }) => void,
    signal?: AbortSignal,
  ) => {
    const res = await fetch(`${BASE_URL}/api/models/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
      signal,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const reader = res.body?.getReader();
    if (!reader) return;
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            onEvent({ type: data.type, data });
          } catch {}
        }
      }
    }
  },

  // Webhooks
  getWebhooks: async () => {
    const res = await request<Record<string, WebhookInfo> | { webhooks?: WebhookInfo[] } | WebhookInfo[]>('/api/webhooks');
    if (Array.isArray(res)) return res;
    if (Array.isArray((res as any).webhooks)) return (res as any).webhooks;
    // Dict format: { "id": { url, events, ... } } — inject id into each object
    const dict = res as Record<string, any>;
    return Object.entries(dict).map(([id, wh]) => ({ ...wh, id }));
  },
  createWebhook: (body: { url: string; events: string[]; secret?: string; max_retries?: number }) =>
    request<WebhookInfo>('/api/webhooks', { method: 'POST', body: JSON.stringify(body) }),
  updateWebhook: (id: string, body: { url: string; events: string[]; secret?: string; max_retries?: number }) =>
    request<WebhookInfo>(`/api/webhooks/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteWebhook: (id: string) =>
    request<void>(`/api/webhooks/${id}`, { method: 'DELETE' }),
  getWebhookDeliveries: () => request<WebhookDelivery[]>('/api/webhooks/log/deliveries'),
  clearWebhookDeliveries: () => request<void>('/api/webhooks/log/deliveries', { method: 'DELETE' }),
};

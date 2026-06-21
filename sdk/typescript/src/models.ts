export interface APIKey {
  key_masked: string;
  provider: string;
  status: string;
  balance?: number;
  models: string[];
  token_limit?: number;
  concurrency_limit?: number;
}

export interface KeyListResponse {
  keys: APIKey[];
  total: number;
  page: number;
  page_size: number;
}

export interface CheckResult {
  key_masked: string;
  valid: boolean;
  provider: string;
  error?: string;
  latency_ms?: number;
}

export interface BalanceResult {
  key_masked: string;
  provider: string;
  balance?: number;
  currency: string;
  error?: string;
}

export interface TestResult {
  key_masked: string;
  provider: string;
  concurrency_limit?: number;
  token_limit?: number;
  error?: string;
}

export interface StatsResponse {
  total_keys: number;
  valid_keys: number;
  invalid_keys: number;
  providers: Record<string, number>;
  by_status: Record<string, number>;
}

export interface ProviderInfo {
  name: string;
  display_name: string;
  website?: string;
  docs?: string;
  models: string[];
}

export interface ProgressResponse {
  total: number;
  completed: number;
  running: number;
  failed: number;
  status: string;
  current_task?: string;
}

export interface LogEntry {
  timestamp: string;
  level: string;
  message: string;
  extra: Record<string, unknown>;
}

export interface OperationLog {
  id: string;
  operation: string;
  status: string;
  started_at: string;
  finished_at?: string;
  details: Record<string, unknown>;
}

export interface ValidationError {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface HTTPValidationError {
  detail: ValidationError[];
}

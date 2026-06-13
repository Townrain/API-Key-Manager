import {
  KeyManagerError as KeyManagerErrorClass,
  AuthenticationError as AuthenticationErrorClass,
  NotFoundError as NotFoundErrorClass,
  ValidationErrorResponse as ValidationErrorResponseClass,
  RateLimitError as RateLimitErrorClass,
  ServerError as ServerErrorClass,
  ConnectionError as ConnectionErrorClass,
} from "./exceptions";

export interface KeyManagerClientOptions {
  baseUrl?: string;
  apiKey?: string;
  timeout?: number;
  maxRetries?: number;
  headers?: Record<string, string>;
}

interface RequestOptions {
  params?: URLSearchParams;
  body?: unknown;
  headers?: Record<string, string>;
}

export class KeyManagerClient {
  private baseUrl: string;
  private apiKey?: string;
  private timeout: number;
  private maxRetries: number;
  private defaultHeaders: Record<string, string>;

  constructor(options: KeyManagerClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8000").replace(/\/+$/, "");
    this.apiKey = options.apiKey;
    this.timeout = options.timeout ?? 30_000;
    this.maxRetries = options.maxRetries ?? 3;
    this.defaultHeaders = {
      Accept: "application/json",
      ...options.headers,
    };
    if (this.apiKey) {
      this.defaultHeaders["Authorization"] = `Bearer ${this.apiKey}`;
    }
  }

  private buildUrl(path: string, params?: URLSearchParams): string {
    const url = new URL(path, this.baseUrl);
    if (params) {
      params.forEach((value, key) => url.searchParams.set(key, value));
    }
    return url.toString();
  }

  private async request(
    method: string,
    path: string,
    options: RequestOptions = {},
  ): Promise<unknown> {
    const retryableStatuses = new Set([429, 502, 503, 504]);
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      const url = this.buildUrl(path, options.params);
      const headers: Record<string, string> = {
        ...this.defaultHeaders,
        ...options.headers,
      };

      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);

      let response: Response;
      try {
        response = await fetch(url, {
          method,
          headers,
          body: options.body ? JSON.stringify(options.body) : undefined,
          signal: controller.signal,
        });
      } catch (err: unknown) {
        clearTimeout(timer);
        lastError = err instanceof Error ? err : new Error(String(err));
        if (err instanceof DOMException && err.name === "AbortError") {
          if (attempt < this.maxRetries) { const d = Math.pow(2, attempt) * 1000; await new Promise(r => setTimeout(r, d)); continue; }
          throw new ConnectionError("Request timed out");
        }
        if (attempt < this.maxRetries) { const d = Math.pow(2, attempt) * 1000; await new Promise(r => setTimeout(r, d)); continue; }
        throw new ConnectionError(`Connection failed: ${err}`);
      } finally {
        clearTimeout(timer);
      }

      if (retryableStatuses.has(response.status) && attempt < this.maxRetries) {
        let delay = Math.pow(2, attempt) * 1000;
        if (response.status === 429) {
          const retryAfter = response.headers.get("Retry-After");
          if (retryAfter) delay = parseFloat(retryAfter) * 1000;
        }
        await new Promise(r => setTimeout(r, delay));
        continue;
      }

      if (response.ok) {
        const ct = response.headers.get("content-type") ?? "";
        if (ct.includes("application/json")) {
          return response.json();
        }
        return { raw: await response.text() };
      }

      await this.handleError(response);
      return {}; // unreachable
    }

    throw new ConnectionError(`Request failed after ${this.maxRetries + 1} attempts: ${lastError}`);
  }

  private async handleError(response: Response): Promise<never> {
    const status = response.status;
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      body = await response.text();
    }
    const msg = `HTTP ${status}: ${JSON.stringify(body)}`;

    if (status === 401) throw new AuthenticationErrorClass(msg, status, body);
    if (status === 404) throw new NotFoundErrorClass(msg, status, body);
    if (status === 422) {
      const errors =
        typeof body === "object" && body !== null && "detail" in body
          ? (body as { detail: unknown[] }).detail
          : [];
      throw new ValidationErrorResponseClass(msg, errors as Record<string, unknown>[], status, body);
    }
    if (status === 429) {
      const retryAfter = response.headers.get("Retry-After");
      throw new RateLimitErrorClass(
        msg,
        retryAfter ? parseFloat(retryAfter) : undefined,
        status,
        body,
      );
    }
    if (status >= 500) throw new ServerErrorClass(msg, status, body);

    throw new KeyManagerErrorClass(msg, status, body);
  }

  /** Api Import */
  async import(file?: string, directory?: string, batch?: unknown[], options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    const body: Record<string, unknown> = {};
    if (file != null) body["file"] = file;
    if (directory != null) body["directory"] = directory;
    if (batch != null) body["batch"] = batch;
    return this.request("POST", "/api/import", { params, body });
  }

  /** Api Import Upload */
  async importUpload(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/import/upload", { params });
  }

  /** Api List Keys */
  async keys(provider?: string, status?: string, batch?: string, page?: number, page_size?: number, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();
    if (provider != null) params.set("provider", String(provider));
    if (status != null) params.set("status", String(status));
    if (batch != null) params.set("batch", String(batch));
    if (page != null) params.set("page", String(page));
    if (page_size != null) params.set("page_size", String(page_size));
    return this.request("GET", "/api/keys", { params });
  }

  /** Api Export Keys */
  async keysExport(provider?: string, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();
    if (provider != null) params.set("provider", String(provider));
    return this.request("GET", "/api/keys/export", { params });
  }

  /** Api Clear Keys */
  async keysClear(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/keys/clear", { params });
  }

  /** Api Check */
  async check(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/check", { params });
  }

  /** Api Check Single */
  async checkSingle(key: string, provider?: string, customBaseUrl?: string, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    const body: Record<string, unknown> = {};
    body["key"] = key;
    if (provider != null) body["provider"] = provider;
    if (customBaseUrl != null) body["custom_base_url"] = customBaseUrl;
    return this.request("POST", "/api/check/single", { params, body });
  }

  /** Api Check Batch */
  async checkBatch(keys: unknown[], timeout?: number, concurrency?: number, customBaseUrl?: string, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    const body: Record<string, unknown> = {};
    body["keys"] = keys;
    if (timeout != null) body["timeout"] = timeout;
    if (concurrency != null) body["concurrency"] = concurrency;
    if (customBaseUrl != null) body["custom_base_url"] = customBaseUrl;
    return this.request("POST", "/api/check/batch", { params, body });
  }

  /** Api Test */
  async test(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/test", { params });
  }

  /** Api Test Single */
  async testSingle(key: string, provider?: string, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    const body: Record<string, unknown> = {};
    body["key"] = key;
    if (provider != null) body["provider"] = provider;
    return this.request("POST", "/api/test/single", { params, body });
  }

  /** Api Test Token */
  async testToken(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/test/token", { params });
  }

  /** Api Test Concurrency */
  async testConcurrency(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/test/concurrency", { params });
  }

  /** Api Balance */
  async balance(key: string, provider?: string, customBaseUrl?: string, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    const body: Record<string, unknown> = {};
    body["key"] = key;
    if (provider != null) body["provider"] = provider;
    if (customBaseUrl != null) body["custom_base_url"] = customBaseUrl;
    return this.request("POST", "/api/balance", { params, body });
  }

  /** Api Models */
  async models(provider?: string, type_filter?: string, key?: string, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();
    if (provider != null) params.set("provider", String(provider));
    if (type_filter != null) params.set("type_filter", String(type_filter));
    if (key != null) params.set("key", String(key));
    return this.request("GET", "/api/models", { params });
  }

  /** Api Models Check */
  async modelsCheck(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("POST", "/api/models/check", { params });
  }

  /** Api Providers */
  async providers(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/providers", { params });
  }

  /** Api Providers Detail */
  async providersDetail(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/providers/detail", { params });
  }

  /** Api Stats */
  async stats(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/stats", { params });
  }

  /** Api Stats Chart */
  async statsChart(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/stats/chart", { params });
  }

  /** Api Progress */
  async progress(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/progress", { params });
  }

  /** Api Progress Stream */
  async progressStream(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/progress/stream", { params });
  }

  /** Api Proxy */
  async proxy(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/proxy", { params });
  }

  /** Api Logs */
  async logs(lines?: number, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();
    if (lines != null) params.set("lines", String(lines));
    return this.request("GET", "/api/logs", { params });
  }

  /** Api Logs Operations */
  async logsOperations(limit?: number, options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();
    if (limit != null) params.set("limit", String(limit));
    return this.request("GET", "/api/logs/operations", { params });
  }

  /** Api Logs Files */
  async logsFiles(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/logs/files", { params });
  }

  /** Api Signature Report */
  async signatureReport(options?: RequestOptions): Promise<unknown> {
    const params = new URLSearchParams();

    return this.request("GET", "/api/signature-report", { params });
  }

}
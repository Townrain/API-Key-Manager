#!/usr/bin/env python3
"""Generate Python and TypeScript SDKs from OpenAPI spec."""

import keyword
import json
import re
from pathlib import Path
from typing import Any


SPEC_PATH = Path(__file__).parent.parent / "docs" / "openapi.json"
SDK_ROOT = Path(__file__).parent.parent / "sdk"


def load_spec() -> dict[str, Any]:
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def to_snake(name: str) -> str:
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower().replace(" ", "_").replace("-", "_")


def safe_name(name: str) -> str:
    """Append underscore if name is a Python keyword."""
    if keyword.iskeyword(name):
        return name + "_"
    return name


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def path_to_method(path: str, method: str, operation_id: str) -> dict[str, Any]:
    clean_path = path.lstrip("/").replace("/", "_").replace("-", "_")
    parts = [p for p in clean_path.split("_") if p and p != "api"]
    fn_name = "_".join(parts) if parts else "index"
    fn_name = to_snake(fn_name).replace("__", "_").strip("_")
    return {
        "path": path,
        "method": method.upper(),
        "operation_id": operation_id,
        "fn_name": fn_name,
        "path_template": path,
    }


def map_python_type(openapi_type: str, nullable: bool = False) -> str:
    """Map OpenAPI type to Python type annotation."""
    type_map: dict[str, str] = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict[str, Any]",
    }
    base = type_map.get(openapi_type, "Any")
    if nullable and base != "Any":
        return f"{base} | None"
    return base


def map_ts_type(openapi_type: str) -> str:
    """Map OpenAPI type to TypeScript type."""
    type_map: dict[str, str] = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "array": "unknown[]",
        "object": "Record<string, unknown>",
    }
    return type_map.get(openapi_type, "unknown")

def extract_endpoints(spec: dict) -> list[dict[str, Any]]:
    endpoints = []
    for path, methods in spec.get("paths", {}).items():
        for method, details in methods.items():
            if method in ("get", "post", "put", "delete", "patch"):
                ep = path_to_method(path, method, details.get("operationId", ""))
                ep["summary"] = details.get("summary", "")
                ep["description"] = details.get("description", "")
                params = details.get("parameters", [])
                ep["params"] = []
                for p in params:
                    ep["params"].append({
                        "name": p["name"],
                        "required": p.get("required", False),
                        "type": p.get("schema", {}).get("type", "string"),
                        "default": p.get("schema", {}).get("default"),
                    })
                ep["body_params"] = []
                request_body = details.get("requestBody", {})
                if request_body:
                    json_content = request_body.get("content", {}).get("application/json", {})
                    schema = json_content.get("schema", {})
                    ref = schema.get("$ref", "")
                    if ref:
                        schema_name = ref.split("/")[-1]
                        comp_schema = spec.get("components", {}).get("schemas", {}).get(schema_name, {})
                        required_fields = comp_schema.get("required", [])
                        for prop_name, prop_schema in comp_schema.get("properties", {}).items():
                            if "anyOf" in prop_schema:
                                types = [t["type"] for t in prop_schema["anyOf"] if t.get("type") != "null"]
                                is_nullable = any(t.get("type") == "null" for t in prop_schema["anyOf"])
                                prop_type = types[0] if types else "string"
                            else:
                                prop_type = prop_schema.get("type", "string")
                                is_nullable = False
                            ep["body_params"].append({
                                "name": prop_name,
                                "type": prop_type,
                                "required": prop_name in required_fields,
                                "default": prop_schema.get("default"),
                                "nullable": is_nullable,
                            })
                endpoints.append(ep)
    return endpoints


# ---------------------------------------------------------------------------
# Python SDK Generation
# ---------------------------------------------------------------------------

def generate_python_models() -> str:
    return '''"""Pydantic models for API Key Manager."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class APIKey(BaseModel):
    key: str
    provider: str = ""
    status: str = "unknown"
    balance: Optional[float] = None
    models: list[str] = Field(default_factory=list)
    token_limit: Optional[int] = None
    concurrency_limit: Optional[int] = None


class KeyListResponse(BaseModel):
    keys: list[APIKey] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50


class CheckResult(BaseModel):
    key: str
    valid: bool
    provider: str = ""
    error: Optional[str] = None
    latency_ms: Optional[float] = None


class BalanceResult(BaseModel):
    key: str
    provider: str
    balance: Optional[float] = None
    currency: str = "USD"
    error: Optional[str] = None


class TestResult(BaseModel):
    key: str
    provider: str
    concurrency_limit: Optional[int] = None
    token_limit: Optional[int] = None
    error: Optional[str] = None


class StatsResponse(BaseModel):
    total_keys: int = 0
    valid_keys: int = 0
    invalid_keys: int = 0
    providers: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)


class ProviderInfo(BaseModel):
    name: str
    display_name: str = ""
    website: Optional[str] = None
    docs: Optional[str] = None
    models: list[str] = Field(default_factory=list)


class ProgressResponse(BaseModel):
    total: int = 0
    completed: int = 0
    running: int = 0
    failed: int = 0
    status: str = "idle"
    current_task: Optional[str] = None


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    extra: dict[str, Any] = Field(default_factory=dict)


class OperationLog(BaseModel):
    id: str
    operation: str
    status: str
    started_at: str
    finished_at: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationError(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class HTTPValidationError(BaseModel):
    detail: list[ValidationError] = Field(default_factory=list)
'''


def generate_python_exceptions() -> str:
    return '''"""Custom exceptions for API Key Manager SDK."""

from __future__ import annotations
from typing import Any, Optional


class KeyManagerError(Exception):
    """Base exception for Key Manager SDK."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class AuthenticationError(KeyManagerError):
    """Raised when authentication fails."""


class NotFoundError(KeyManagerError):
    """Raised when a resource is not found."""


class ValidationError(KeyManagerError):
    """Raised when request validation fails."""

    def __init__(self, message: str, errors: Optional[list[dict]] = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.errors = errors or []


class RateLimitError(KeyManagerError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str, retry_after: Optional[float] = None, **kwargs: Any):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ServerError(KeyManagerError):
    """Raised on 5xx server errors."""


class ConnectionError(KeyManagerError):
    """Raised when connection to server fails."""
'''


def generate_python_client(endpoints: list[dict[str, Any]]) -> str:
    lines = []
    lines.append('"""API Key Manager SDK Client."""')
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from typing import Any, Optional")
    lines.append("import logging")
    lines.append("import time")
    lines.append("import httpx")
    lines.append("")
    lines.append("from .exceptions import (")
    lines.append("    AuthenticationError,")
    lines.append("    ConnectionError,")
    lines.append("    KeyManagerError,")
    lines.append("    NotFoundError,")
    lines.append("    RateLimitError,")
    lines.append("    ServerError,")
    lines.append("    ValidationError,")
    lines.append(")")
    lines.append("")
    lines.append("")
    lines.append("class KeyManagerClient:")
    lines.append('    """Client for the API Key Manager service.')
    lines.append("")
    lines.append("    Args:")
    lines.append("        base_url: Base URL of the API (e.g. http://localhost:8000)")
    lines.append("        api_key: Optional API key for authentication")
    lines.append("        timeout: Request timeout in seconds")
    lines.append('    """')
    lines.append("")
    lines.append("    def __init__(")
    lines.append("        self,")
    lines.append('        base_url: str = "http://localhost:8000",')
    lines.append("        api_key: Optional[str] = None,")
    lines.append("        timeout: float = 30.0,")
    lines.append("        max_retries: int = 3,")
    lines.append("    ) -> None:")
    lines.append('        self.base_url = base_url.rstrip("/")')
    lines.append("        self.api_key = api_key")
    lines.append("        self.max_retries = max_retries")
    lines.append("        self._logger = logging.getLogger(__name__)")
    lines.append("        self._client = httpx.Client(")
    lines.append("            base_url=self.base_url,")
    lines.append("            timeout=timeout,")
    lines.append("            headers=self._build_headers(),")
    lines.append("        )")
    lines.append("")
    lines.append("    def _build_headers(self) -> dict[str, str]:")
    lines.append('        headers: dict[str, str] = {"Accept": "application/json"}')
    lines.append("        if self.api_key:")
    lines.append('            headers["Authorization"] = f"Bearer {self.api_key}"')
    lines.append("        return headers")
    lines.append("")
    lines.append("    def _request(")
    lines.append("        self,")
    lines.append("        method: str,")
    lines.append("        path: str,")
    lines.append("        params: Optional[dict[str, Any]] = None,")
    lines.append("        json_body: Optional[dict[str, Any]] = None,")
    lines.append("        **kwargs: Any,")
    lines.append("    ) -> dict[str, Any]:")
    lines.append("        retryable_statuses = {429, 502, 503, 504}")
    lines.append("        last_exception: Optional[Exception] = None")
    lines.append("")
    lines.append("        for attempt in range(self.max_retries + 1):")
    lines.append("            try:")
    lines.append("                resp = self._client.request(")
    lines.append("                    method, path, params=params, json=json_body, **kwargs")
    lines.append("                )")
    lines.append("            except (httpx.ConnectError, httpx.ReadTimeout) as exc:")
    lines.append("                last_exception = exc")
    lines.append("                if attempt < self.max_retries:")
    lines.append("                    delay = 2 ** attempt")
    lines.append("                    self._logger.warning(")
    lines.append("                        \"Request %s %s failed (attempt %d/%d): %s. Retrying in %ds...\",")
    lines.append("                        method, path, attempt + 1, self.max_retries + 1, exc, delay,")
    lines.append("                    )")
    lines.append("                    time.sleep(delay)")
    lines.append("                    continue")
    lines.append("                raise ConnectionError(f\"Connection failed: {exc}\") from exc")
    lines.append("")
    lines.append("            if resp.status_code in retryable_statuses and attempt < self.max_retries:")
    lines.append("                if resp.status_code == 429:")
    lines.append("                    retry_after = resp.headers.get(\"Retry-After\")")
    lines.append("                    delay = float(retry_after) if retry_after else 2 ** attempt")
    lines.append("                else:")
    lines.append("                    delay = 2 ** attempt")
    lines.append("                self._logger.warning(")
    lines.append("                    \"Request %s %s returned %d (attempt %d/%d). Retrying in %ds...\",")
    lines.append("                    method, path, resp.status_code, attempt + 1, self.max_retries + 1, delay,")
    lines.append("                )")
    lines.append("                time.sleep(delay)")
    lines.append("                continue")
    lines.append("")
    lines.append("            if resp.status_code == 200:")
    lines.append('                ct = resp.headers.get("content-type", "")')
    lines.append('                if "application/json" in ct:')
    lines.append("                    return resp.json()")
    lines.append("                return {\"raw\": resp.text}")
    lines.append("")
    lines.append("            self._raise_for_status(resp)")
    lines.append("            return {}  # unreachable")
    lines.append("")
    lines.append("        # All retries exhausted")
    lines.append("        if last_exception:")
    lines.append("            raise ConnectionError(f\"Connection failed after {self.max_retries + 1} attempts: {last_exception}\") from last_exception")
    lines.append("        return {}  # unreachable")
    lines.append("")
    lines.append("    def _raise_for_status(self, resp: httpx.Response) -> None:")
    lines.append("        status = resp.status_code")
    lines.append("        try:")
    lines.append("            body = resp.json()")
    lines.append("        except Exception:")
    lines.append("            body = resp.text")
    lines.append("")
    lines.append('        msg = f"HTTP {status}: {body}"')
    lines.append("")
    lines.append("        if status == 401:")
    lines.append("            raise AuthenticationError(msg, status_code=status, body=body)")
    lines.append("        if status == 404:")
    lines.append("            raise NotFoundError(msg, status_code=status, body=body)")
    lines.append("        if status == 422:")
    lines.append('            errors = body.get("detail", []) if isinstance(body, dict) else []')
    lines.append("            raise ValidationError(msg, errors=errors, status_code=status, body=body)")
    lines.append("        if status == 429:")
    lines.append('            retry_after = resp.headers.get("Retry-After")')
    lines.append("            raise RateLimitError(")
    lines.append("                msg,")
    lines.append("                retry_after=float(retry_after) if retry_after else None,")
    lines.append("                status_code=status,")
    lines.append("                body=body,")
    lines.append("            )")
    lines.append("        if status >= 500:")
    lines.append("            raise ServerError(msg, status_code=status, body=body)")
    lines.append("")
    lines.append("        raise KeyManagerError(msg, status_code=status, body=body)")
    lines.append("")
    lines.append("    def close(self) -> None:")
    lines.append('        """Close the underlying HTTP client."""')
    lines.append("        self._client.close()")
    lines.append("")
    lines.append("    def __enter__(self) -> KeyManagerClient:")
    lines.append("        return self")
    lines.append("")
    lines.append("    def __exit__(self, *args: Any) -> None:")
    lines.append("        self.close()")
    lines.append("")

    for ep in endpoints:
        fn = safe_name(ep["fn_name"])
        params_sig = ["self"]
        for p in ep["params"]:
            pname = p["name"]
            ptype = "str" if p["type"] == "string" else "int"
            pdefault = p["default"]
            default = f" = {repr(pdefault)}" if pdefault is not None else (" = None" if not p["required"] else "")
            params_sig.append(f"{pname}: {ptype}{default}")
        body_params = ep.get("body_params", [])
        for bp in body_params:
            bp_name = bp["name"]
            py_type = map_python_type(bp["type"], bp.get("nullable", False))
            if bp["required"]:
                default_str = ""
            elif bp.get("nullable"):
                default_str = " = None"
            elif bp.get("default") is not None:
                bp_default = bp["default"]
                if bp["type"] == "string":
                    default_str = f" = {repr(bp_default)}"
                else:
                    default_str = f" = {bp_default}"
            else:
                if bp["type"] == "string":
                    default_str = ' = ""'
                elif bp["type"] == "boolean":
                    default_str = " = False"
                elif bp["type"] in ("integer", "number"):
                    default_str = " = None" if bp.get("nullable") else " = 0"
                else:
                    default_str = " = None"
            params_sig.append(f"{bp_name}: {py_type}{default_str}")
        params_sig.append("**kwargs: Any")
        sig = ", ".join(params_sig)

        summary = ep["summary"] or fn
        method = ep["method"]
        path = ep["path"]

        lines.append(f"    def {fn}({sig}) -> dict[str, Any]:")
        lines.append(f'        """{summary}"""')
        lines.append("        params: dict[str, Any] = {}")
        for p in ep["params"]:
            pname = p["name"]
            lines.append(f'        if {pname} is not None: params["{pname}"] = {pname}')
        if body_params:
            lines.append("        json_body: dict[str, Any] = {}")
            for bp in body_params:
                bp_name = bp["name"]
                if bp["required"]:
                    lines.append(f'        json_body["{bp_name}"] = {bp_name}')
                elif bp.get("nullable"):
                    lines.append(f'        if {bp_name} is not None: json_body["{bp_name}"] = {bp_name}')
                elif bp["type"] == "string":
                    lines.append(f'        if {bp_name}: json_body["{bp_name}"] = {bp_name}')
                else:
                    lines.append(f'        if {bp_name}: json_body["{bp_name}"] = {bp_name}')
            call_parts = [f'"{method}"', f'"{path}"', "params=params", "json_body=json_body", "**kwargs"]
        else:
            call_parts = [f'"{method}"', f'"{path}"', "params=params", "**kwargs"]
        call_str = ", ".join(call_parts)
        lines.append(f"        return self._request({call_str})")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# TypeScript SDK Generation
# ---------------------------------------------------------------------------

def generate_ts_models() -> str:
    return '''export interface APIKey {
  key: string;
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
  key: string;
  valid: boolean;
  provider: string;
  error?: string;
  latency_ms?: number;
}

export interface BalanceResult {
  key: string;
  provider: string;
  balance?: number;
  currency: string;
  error?: string;
}

export interface TestResult {
  key: string;
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
'''


def generate_ts_exceptions() -> str:
    return '''export class KeyManagerError extends Error {
  statusCode?: number;
  body?: unknown;

  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message);
    this.name = "KeyManagerError";
    this.statusCode = statusCode;
    this.body = body;
  }
}

export class AuthenticationError extends KeyManagerError {
  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "AuthenticationError";
  }
}

export class NotFoundError extends KeyManagerError {
  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "NotFoundError";
  }
}

export class ValidationErrorResponse extends KeyManagerError {
  errors: Record<string, unknown>[];

  constructor(message: string, errors: Record<string, unknown>[] = [], statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "ValidationError";
    this.errors = errors;
  }
}

export class RateLimitError extends KeyManagerError {
  retryAfter?: number;

  constructor(message: string, retryAfter?: number, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "RateLimitError";
    this.retryAfter = retryAfter;
  }
}

export class ServerError extends KeyManagerError {
  constructor(message: string, statusCode?: number, body?: unknown) {
    super(message, statusCode, body);
    this.name = "ServerError";
  }
}

export class ConnectionError extends KeyManagerError {
  constructor(message: string) {
    super(message);
    this.name = "ConnectionError";
  }
}
'''


def generate_ts_client(endpoints: list[dict[str, Any]]) -> str:
    lines = []
    lines.append('import {')
    lines.append('  KeyManagerError as KeyManagerErrorClass,')
    lines.append('  AuthenticationError as AuthenticationErrorClass,')
    lines.append('  NotFoundError as NotFoundErrorClass,')
    lines.append('  ValidationErrorResponse as ValidationErrorResponseClass,')
    lines.append('  RateLimitError as RateLimitErrorClass,')
    lines.append('  ServerError as ServerErrorClass,')
    lines.append('  ConnectionError as ConnectionErrorClass,')
    lines.append('} from "./exceptions";')
    lines.append('')
    lines.append('export interface KeyManagerClientOptions {')
    lines.append('  baseUrl?: string;')
    lines.append('  apiKey?: string;')
    lines.append('  timeout?: number;')
    lines.append('  maxRetries?: number;')
    lines.append('  headers?: Record<string, string>;')
    lines.append('}')
    lines.append('')
    lines.append('interface RequestOptions {')
    lines.append('  params?: URLSearchParams;')
    lines.append('  body?: unknown;')
    lines.append('  headers?: Record<string, string>;')
    lines.append('}')
    lines.append('')
    lines.append('export class KeyManagerClient {')
    lines.append('  private baseUrl: string;')
    lines.append('  private apiKey?: string;')
    lines.append('  private timeout: number;')
    lines.append('  private maxRetries: number;')
    lines.append('  private defaultHeaders: Record<string, string>;')
    lines.append('')
    lines.append('  constructor(options: KeyManagerClientOptions = {}) {')
    lines.append('    this.baseUrl = (options.baseUrl ?? "http://localhost:8000").replace(/\\/+$/, "");')
    lines.append('    this.apiKey = options.apiKey;')
    lines.append('    this.timeout = options.timeout ?? 30_000;')
    lines.append('    this.maxRetries = options.maxRetries ?? 3;')
    lines.append('    this.defaultHeaders = {')
    lines.append('      Accept: "application/json",')
    lines.append('      ...options.headers,')
    lines.append('    };')
    lines.append('    if (this.apiKey) {')
    lines.append('      this.defaultHeaders["Authorization"] = `Bearer ${this.apiKey}`;')
    lines.append('    }')
    lines.append('  }')
    lines.append('')
    lines.append('  private buildUrl(path: string, params?: URLSearchParams): string {')
    lines.append('    const url = new URL(path, this.baseUrl);')
    lines.append('    if (params) {')
    lines.append('      params.forEach((value, key) => url.searchParams.set(key, value));')
    lines.append('    }')
    lines.append('    return url.toString();')
    lines.append('  }')
    lines.append('')
    lines.append('  private async request(')
    lines.append('    method: string,')
    lines.append('    path: string,')
    lines.append('    options: RequestOptions = {},')
    lines.append('  ): Promise<unknown> {')
    lines.append('    const retryableStatuses = new Set([429, 502, 503, 504]);')
    lines.append('    let lastError: Error | null = null;')
    lines.append('')
    lines.append('    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {')
    lines.append('      const url = this.buildUrl(path, options.params);')
    lines.append('      const headers: Record<string, string> = {')
    lines.append('        ...this.defaultHeaders,')
    lines.append('        ...options.headers,')
    lines.append('      };')
    lines.append('')
    lines.append('      const controller = new AbortController();')
    lines.append('      const timer = setTimeout(() => controller.abort(), this.timeout);')
    lines.append('')
    lines.append('      let response: Response;')
    lines.append('      try {')
    lines.append('        response = await fetch(url, {')
    lines.append('          method,')
    lines.append('          headers,')
    lines.append('          body: options.body ? JSON.stringify(options.body) : undefined,')
    lines.append('          signal: controller.signal,')
    lines.append('        });')
    lines.append('      } catch (err: unknown) {')
    lines.append('        clearTimeout(timer);')
    lines.append('        lastError = err instanceof Error ? err : new Error(String(err));')
    lines.append('        if (err instanceof DOMException && err.name === "AbortError") {')
    lines.append('          if (attempt < this.maxRetries) { const d = Math.pow(2, attempt) * 1000; await new Promise(r => setTimeout(r, d)); continue; }')
    lines.append('          throw new ConnectionError("Request timed out");')
    lines.append('        }')
    lines.append('        if (attempt < this.maxRetries) { const d = Math.pow(2, attempt) * 1000; await new Promise(r => setTimeout(r, d)); continue; }')
    lines.append('        throw new ConnectionError(`Connection failed: ${err}`);')
    lines.append('      } finally {')
    lines.append('        clearTimeout(timer);')
    lines.append('      }')
    lines.append('')
    lines.append('      if (retryableStatuses.has(response.status) && attempt < this.maxRetries) {')
    lines.append('        let delay = Math.pow(2, attempt) * 1000;')
    lines.append('        if (response.status === 429) {')
    lines.append('          const retryAfter = response.headers.get("Retry-After");')
    lines.append('          if (retryAfter) delay = parseFloat(retryAfter) * 1000;')
    lines.append('        }')
    lines.append('        await new Promise(r => setTimeout(r, delay));')
    lines.append('        continue;')
    lines.append('      }')
    lines.append('')
    lines.append('      if (response.ok) {')
    lines.append('        const ct = response.headers.get("content-type") ?? "";')
    lines.append('        if (ct.includes("application/json")) {')
    lines.append('          return response.json();')
    lines.append('        }')
    lines.append('        return { raw: await response.text() };')
    lines.append('      }')
    lines.append('')
    lines.append('      await this.handleError(response);')
    lines.append('      return {}; // unreachable')
    lines.append('    }')
    lines.append('')
    lines.append('    throw new ConnectionError(`Request failed after ${this.maxRetries + 1} attempts: ${lastError}`);')
    lines.append('  }')
    lines.append('')
    lines.append('  private async handleError(response: Response): Promise<never> {')
    lines.append('    const status = response.status;')
    lines.append('    let body: unknown;')
    lines.append('    try {')
    lines.append('      body = await response.json();')
    lines.append('    } catch {')
    lines.append('      body = await response.text();')
    lines.append('    }')
    lines.append('    const msg = `HTTP ${status}: ${JSON.stringify(body)}`;')
    lines.append('')
    lines.append('    if (status === 401) throw new AuthenticationErrorClass(msg, status, body);')
    lines.append('    if (status === 404) throw new NotFoundErrorClass(msg, status, body);')
    lines.append('    if (status === 422) {')
    lines.append('      const errors =')
    lines.append('        typeof body === "object" && body !== null && "detail" in body')
    lines.append('          ? (body as { detail: unknown[] }).detail')
    lines.append('          : [];')
    lines.append('      throw new ValidationErrorResponseClass(msg, errors as Record<string, unknown>[], status, body);')
    lines.append('    }')
    lines.append('    if (status === 429) {')
    lines.append('      const retryAfter = response.headers.get("Retry-After");')
    lines.append('      throw new RateLimitErrorClass(')
    lines.append('        msg,')
    lines.append('        retryAfter ? parseFloat(retryAfter) : undefined,')
    lines.append('        status,')
    lines.append('        body,')
    lines.append('      );')
    lines.append('    }')
    lines.append('    if (status >= 500) throw new ServerErrorClass(msg, status, body);')
    lines.append('')
    lines.append('    throw new KeyManagerErrorClass(msg, status, body);')
    lines.append('  }')
    lines.append('')

    for ep in endpoints:
        fn = to_camel(ep["fn_name"])
        params_parts = []
        query_parts = []
        for p in ep["params"]:
            pname = p["name"]
            ptype = "string" if p["type"] == "string" else "number"
            optional = "?" if not p["required"] or p["default"] is not None else ""
            params_parts.append(f"{pname}{optional}: {ptype}")
            query_parts.append(f"    if ({pname} != null) params.set(\"{pname}\", String({pname}));")
        body_params = ep.get("body_params", [])
        for bp in body_params:
            bp_name = bp["name"]
            ts_name = to_camel(bp_name)
            ts_type = map_ts_type(bp["type"])
            optional_marker = "?" if not bp["required"] else ""
            params_parts.append(f"{ts_name}{optional_marker}: {ts_type}")
        params_sig = ", ".join(params_parts) if params_parts else ""
        if params_sig:
            params_sig += ", "
        params_sig += "options?: RequestOptions"

        summary = ep["summary"] or fn
        method = ep["method"]
        path = ep["path"]

        query_block = "\n".join(query_parts)

        lines.append(f"  /** {summary} */")
        lines.append(f"  async {fn}({params_sig}): Promise<unknown> {{")
        lines.append("    const params = new URLSearchParams();")
        lines.append(query_block)
        if body_params:
            lines.append("    const body: Record<string, unknown> = {};")
            for bp in body_params:
                bp_name = bp["name"]
                ts_name = to_camel(bp_name)
                if bp["required"]:
                    lines.append(f"    body[\"{bp_name}\"] = {ts_name};")
                else:
                    lines.append(f"    if ({ts_name} != null) body[\"{bp_name}\"] = {ts_name};")
            lines.append(f"    return this.request(\"{method}\", \"{path}\", {{ params, body }});")
        else:
            lines.append(f"    return this.request(\"{method}\", \"{path}\", {{ params }});")
        lines.append("  }")
        lines.append("")

    lines.append("}")
    return "\n".join(lines)


def generate_ts_index() -> str:
    return '''export { KeyManagerClient } from "./client";
export type { KeyManagerClientOptions } from "./client";
export * from "./models";
export * from "./exceptions";
'''


def generate_ts_package_json() -> str:
    return '''{
  "name": "@api-key-manager/sdk",
  "version": "1.0.0",
  "description": "TypeScript SDK for API Key Manager",
  "main": "dist/index.js",
  "types": "dist/index.d.ts",
  "files": ["dist"],
  "scripts": {
    "build": "tsc",
    "prepublishOnly": "npm run build"
  },
  "keywords": ["api-key", "key-manager", "sdk"],
  "license": "MIT",
  "devDependencies": {
    "typescript": "^5.4.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
'''


def generate_python_init() -> str:
    return '''"""API Key Manager Python SDK."""

from .client import KeyManagerClient
from .exceptions import (
    AuthenticationError,
    ConnectionError,
    KeyManagerError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .models import (
    APIKey,
    BalanceResult,
    CheckResult,
    HTTPValidationError,
    KeyListResponse,
    LogEntry,
    OperationLog,
    ProgressResponse,
    ProviderInfo,
    StatsResponse,
    TestResult,
    ValidationError as ValidationErrorModel,
)

__all__ = [
    "KeyManagerClient",
    "KeyManagerError",
    "AuthenticationError",
    "ConnectionError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
    "APIKey",
    "BalanceResult",
    "CheckResult",
    "HTTPValidationError",
    "KeyListResponse",
    "LogEntry",
    "OperationLog",
    "ProgressResponse",
    "ProviderInfo",
    "StatsResponse",
    "TestResult",
    "ValidationErrorModel",
]

__version__ = "1.0.0"
'''


def generate_python_pyproject() -> str:
    return '''[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "key-manager-sdk"
version = "1.0.0"
description = "Python SDK for API Key Manager"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
dependencies = [
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "mypy>=1.8.0",
    "ruff>=0.3.0",
]
'''


def generate_readme(spec: dict, endpoints: list[dict[str, Any]]) -> str:
    info = spec.get("info", {})
    title = info.get("title", "API Key Manager")
    version = info.get("version", "1.0.0")
    desc = info.get("description", "")

    table_rows = []
    for ep in endpoints:
        fn = ep["fn_name"]
        ts_fn = to_camel(fn)
        table_rows.append(f"| `{fn}` / `{ts_fn}` | {ep['method']} `{ep['path']}` | {ep['summary']} |")
    table = "\n".join(table_rows)

    return f'''# {title} SDK

{desc}

Version: {version}

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
import {{ KeyManagerClient }} from "@api-key-manager/sdk";

const client = new KeyManagerClient({{
  baseUrl: "http://localhost:8000",
}});

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
    print(f"Validation errors: {{e.errors}}")
except RateLimitError as e:
    print(f"Rate limited, retry after {{e.retry_after}}s")
except ServerError:
    print("Server error")
except KeyManagerError as e:
    print(f"API error: {{e}}")
```

### TypeScript

```typescript
import {{
  KeyManagerClient,
  KeyManagerError,
  AuthenticationError,
  NotFoundError,
  ValidationErrorResponse,
  RateLimitError,
  ServerError,
}} from "@api-key-manager/sdk";

const client = new KeyManagerClient({{ baseUrl: "http://localhost:8000" }});

try {{
  const result = await client.checkSingleKey();
}} catch (err) {{
  if (err instanceof AuthenticationError) {{
    console.error("Invalid API key");
  }} else if (err instanceof NotFoundError) {{
    console.error("Resource not found");
  }} else if (err instanceof ValidationErrorResponse) {{
    console.error("Validation errors:", err.errors);
  }} else if (err instanceof RateLimitError) {{
    console.error(`Rate limited, retry after ${{err.retryAfter}}s`);
  }} else if (err instanceof ServerError) {{
    console.error("Server error");
  }} else if (err instanceof KeyManagerError) {{
    console.error("API error:", err.message);
  }}
}}
```

## API Reference

| Python Method | TypeScript Method | HTTP | Path | Description |
|---|---|---|---|---|
{table}

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
'''


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  wrote {path}")


def main() -> None:
    print("Loading OpenAPI spec...")
    spec = load_spec()
    endpoints = extract_endpoints(spec)
    print(f"Found {len(endpoints)} endpoints\n")

    print("Generating Python SDK...")
    py_dir = SDK_ROOT / "python"
    write_file(py_dir / "pyproject.toml", generate_python_pyproject())
    write_file(py_dir / "key_manager_sdk" / "__init__.py", generate_python_init())
    write_file(py_dir / "key_manager_sdk" / "models.py", generate_python_models())
    write_file(py_dir / "key_manager_sdk" / "exceptions.py", generate_python_exceptions())
    write_file(py_dir / "key_manager_sdk" / "client.py", generate_python_client(endpoints))

    print("\nGenerating TypeScript SDK...")
    ts_dir = SDK_ROOT / "typescript"
    write_file(ts_dir / "package.json", generate_ts_package_json())
    write_file(ts_dir / "src" / "index.ts", generate_ts_index())
    write_file(ts_dir / "src" / "models.ts", generate_ts_models())
    write_file(ts_dir / "src" / "exceptions.ts", generate_ts_exceptions())
    write_file(ts_dir / "src" / "client.ts", generate_ts_client(endpoints))

    print("\nGenerating README...")
    write_file(SDK_ROOT / "README.md", generate_readme(spec, endpoints))

    print("\nDone!")


if __name__ == "__main__":
    main()

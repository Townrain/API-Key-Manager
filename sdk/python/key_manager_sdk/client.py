"""API Key Manager SDK Client."""

from __future__ import annotations

from typing import Any, Optional
import logging
import time
import httpx

from .exceptions import (
    AuthenticationError,
    ConnectionError,
    KeyManagerError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)


class KeyManagerClient:
    """Client for the API Key Manager service.

    Args:
        base_url: Base URL of the API (e.g. http://localhost:8000)
        api_key: Optional API key for authentication
        timeout: Request timeout in seconds
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.max_retries = max_retries
        self._logger = logging.getLogger(__name__)
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._build_headers(),
        )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        retryable_statuses = {429, 502, 503, 504}
        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self._client.request(
                    method, path, params=params, json=json_body, **kwargs
                )
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    delay = 2 ** attempt
                    self._logger.warning(
                        "Request %s %s failed (attempt %d/%d): %s. Retrying in %ds...",
                        method, path, attempt + 1, self.max_retries + 1, exc, delay,
                    )
                    time.sleep(delay)
                    continue
                raise ConnectionError(f"Connection failed: {exc}") from exc

            if resp.status_code in retryable_statuses and attempt < self.max_retries:
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else 2 ** attempt
                else:
                    delay = 2 ** attempt
                self._logger.warning(
                    "Request %s %s returned %d (attempt %d/%d). Retrying in %ds...",
                    method, path, resp.status_code, attempt + 1, self.max_retries + 1, delay,
                )
                time.sleep(delay)
                continue

            if resp.status_code == 200:
                ct = resp.headers.get("content-type", "")
                if "application/json" in ct:
                    return resp.json()
                return {"raw": resp.text}

            self._raise_for_status(resp)
            return {}  # unreachable

        # All retries exhausted
        if last_exception:
            raise ConnectionError(f"Connection failed after {self.max_retries + 1} attempts: {last_exception}") from last_exception
        return {}  # unreachable

    def _raise_for_status(self, resp: httpx.Response) -> None:
        status = resp.status_code
        try:
            body = resp.json()
        except Exception:
            body = resp.text

        msg = f"HTTP {status}: {body}"

        if status == 401:
            raise AuthenticationError(msg, status_code=status, body=body)
        if status == 404:
            raise NotFoundError(msg, status_code=status, body=body)
        if status == 422:
            errors = body.get("detail", []) if isinstance(body, dict) else []
            raise ValidationError(msg, errors=errors, status_code=status, body=body)
        if status == 429:
            retry_after = resp.headers.get("Retry-After")
            raise RateLimitError(
                msg,
                retry_after=float(retry_after) if retry_after else None,
                status_code=status,
                body=body,
            )
        if status >= 500:
            raise ServerError(msg, status_code=status, body=body)

        raise KeyManagerError(msg, status_code=status, body=body)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> KeyManagerClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def import_(self, file: str | None = None, directory: str | None = None, batch: list | None = None, **kwargs: Any) -> dict[str, Any]:
        """Api Import"""
        params: dict[str, Any] = {}
        json_body: dict[str, Any] = {}
        if file is not None: json_body["file"] = file
        if directory is not None: json_body["directory"] = directory
        if batch is not None: json_body["batch"] = batch
        return self._request("POST", "/api/import", params=params, json_body=json_body, **kwargs)

    def import_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Api Import Upload"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/import/upload", params=params, **kwargs)

    def keys(self, provider: str = None, status: str = None, batch: str = None, page: int = 1, page_size: int = 50, **kwargs: Any) -> dict[str, Any]:
        """Api List Keys"""
        params: dict[str, Any] = {}
        if provider is not None: params["provider"] = provider
        if status is not None: params["status"] = status
        if batch is not None: params["batch"] = batch
        if page is not None: params["page"] = page
        if page_size is not None: params["page_size"] = page_size
        return self._request("GET", "/api/keys", params=params, **kwargs)

    def keys_export(self, provider: str = None, **kwargs: Any) -> dict[str, Any]:
        """Api Export Keys"""
        params: dict[str, Any] = {}
        if provider is not None: params["provider"] = provider
        return self._request("GET", "/api/keys/export", params=params, **kwargs)

    def keys_clear(self, **kwargs: Any) -> dict[str, Any]:
        """Api Clear Keys"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/keys/clear", params=params, **kwargs)

    def check(self, **kwargs: Any) -> dict[str, Any]:
        """Api Check"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/check", params=params, **kwargs)

    def check_single(self, key: str, provider: str = '', custom_base_url: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Api Check Single"""
        params: dict[str, Any] = {}
        json_body: dict[str, Any] = {}
        json_body["key"] = key
        if provider: json_body["provider"] = provider
        if custom_base_url is not None: json_body["custom_base_url"] = custom_base_url
        return self._request("POST", "/api/check/single", params=params, json_body=json_body, **kwargs)

    def check_batch(self, keys: list, timeout: int = 10, concurrency: int = 50, custom_base_url: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Api Check Batch"""
        params: dict[str, Any] = {}
        json_body: dict[str, Any] = {}
        json_body["keys"] = keys
        if timeout: json_body["timeout"] = timeout
        if concurrency: json_body["concurrency"] = concurrency
        if custom_base_url is not None: json_body["custom_base_url"] = custom_base_url
        return self._request("POST", "/api/check/batch", params=params, json_body=json_body, **kwargs)

    def test(self, **kwargs: Any) -> dict[str, Any]:
        """Api Test"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/test", params=params, **kwargs)

    def test_single(self, key: str, provider: str = '', **kwargs: Any) -> dict[str, Any]:
        """Api Test Single"""
        params: dict[str, Any] = {}
        json_body: dict[str, Any] = {}
        json_body["key"] = key
        if provider: json_body["provider"] = provider
        return self._request("POST", "/api/test/single", params=params, json_body=json_body, **kwargs)

    def test_token(self, **kwargs: Any) -> dict[str, Any]:
        """Api Test Token"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/test/token", params=params, **kwargs)

    def test_concurrency(self, **kwargs: Any) -> dict[str, Any]:
        """Api Test Concurrency"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/test/concurrency", params=params, **kwargs)

    def balance(self, key: str, provider: str = '', custom_base_url: str | None = None, **kwargs: Any) -> dict[str, Any]:
        """Api Balance"""
        params: dict[str, Any] = {}
        json_body: dict[str, Any] = {}
        json_body["key"] = key
        if provider: json_body["provider"] = provider
        if custom_base_url is not None: json_body["custom_base_url"] = custom_base_url
        return self._request("POST", "/api/balance", params=params, json_body=json_body, **kwargs)

    def models(self, provider: str = None, type_filter: str = 'all', key: str = None, **kwargs: Any) -> dict[str, Any]:
        """Api Models"""
        params: dict[str, Any] = {}
        if provider is not None: params["provider"] = provider
        if type_filter is not None: params["type_filter"] = type_filter
        if key is not None: params["key"] = key
        return self._request("GET", "/api/models", params=params, **kwargs)

    def models_check(self, **kwargs: Any) -> dict[str, Any]:
        """Api Models Check"""
        params: dict[str, Any] = {}
        return self._request("POST", "/api/models/check", params=params, **kwargs)

    def providers(self, **kwargs: Any) -> dict[str, Any]:
        """Api Providers"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/providers", params=params, **kwargs)

    def providers_detail(self, **kwargs: Any) -> dict[str, Any]:
        """Api Providers Detail"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/providers/detail", params=params, **kwargs)

    def stats(self, **kwargs: Any) -> dict[str, Any]:
        """Api Stats"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/stats", params=params, **kwargs)

    def stats_chart(self, **kwargs: Any) -> dict[str, Any]:
        """Api Stats Chart"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/stats/chart", params=params, **kwargs)

    def progress(self, **kwargs: Any) -> dict[str, Any]:
        """Api Progress"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/progress", params=params, **kwargs)

    def progress_stream(self, **kwargs: Any) -> dict[str, Any]:
        """Api Progress Stream"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/progress/stream", params=params, **kwargs)

    def proxy(self, **kwargs: Any) -> dict[str, Any]:
        """Api Proxy"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/proxy", params=params, **kwargs)

    def logs(self, lines: int = 100, **kwargs: Any) -> dict[str, Any]:
        """Api Logs"""
        params: dict[str, Any] = {}
        if lines is not None: params["lines"] = lines
        return self._request("GET", "/api/logs", params=params, **kwargs)

    def logs_operations(self, limit: int = 50, **kwargs: Any) -> dict[str, Any]:
        """Api Logs Operations"""
        params: dict[str, Any] = {}
        if limit is not None: params["limit"] = limit
        return self._request("GET", "/api/logs/operations", params=params, **kwargs)

    def logs_files(self, **kwargs: Any) -> dict[str, Any]:
        """Api Logs Files"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/logs/files", params=params, **kwargs)

    def signature_report(self, **kwargs: Any) -> dict[str, Any]:
        """Api Signature Report"""
        params: dict[str, Any] = {}
        return self._request("GET", "/api/signature-report", params=params, **kwargs)

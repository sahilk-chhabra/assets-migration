from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request


@dataclass
class ApiError(Exception):
    status_code: int | None
    message: str
    url: str
    response_body: str | None = None

    def __str__(self) -> str:
        status = self.status_code if self.status_code is not None else "N/A"
        return f"ApiError(status={status}, url={self.url}, message={self.message})"


class HttpClient:
    """Small HTTP helper with JSON support and retry behavior."""

    def __init__(self, timeout_seconds: int = 30, max_retries: int = 3, backoff_factor: int = 2):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
        data: bytes | None = None,
    ) -> dict[str, Any] | list[Any] | str | None:
        request_headers = dict(headers or {})
        target_url = self._build_url(url, params)

        payload: bytes | None = data
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        req = request.Request(target_url, method=method.upper(), headers=request_headers, data=payload)

        for attempt in range(self.max_retries + 1):
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = response.read()
                    if not raw:
                        return None
                    return self._decode_response(raw)
            except error.HTTPError as exc:
                body = self._read_error_body(exc)
                # Retry only for transient server errors.
                if 500 <= exc.code <= 599 and attempt < self.max_retries:
                    self._sleep(attempt)
                    continue
                raise ApiError(
                    status_code=exc.code,
                    message=exc.reason or "HTTP error",
                    url=target_url,
                    response_body=body,
                ) from exc
            except (error.URLError, TimeoutError) as exc:
                if attempt < self.max_retries:
                    self._sleep(attempt)
                    continue
                raise ApiError(
                    status_code=None,
                    message=str(exc),
                    url=target_url,
                    response_body=None,
                ) from exc

        raise ApiError(status_code=None, message="Request failed after retries", url=target_url)

    @staticmethod
    def _build_url(url: str, params: dict[str, Any] | None) -> str:
        if not params:
            return url
        encoded = parse.urlencode({k: v for k, v in params.items() if v is not None})
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}{encoded}"

    @staticmethod
    def _decode_response(raw: bytes) -> dict[str, Any] | list[Any] | str:
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    @staticmethod
    def _read_error_body(exc: error.HTTPError) -> str | None:
        try:
            return exc.read().decode("utf-8", errors="replace")
        except Exception:
            return None

    def _sleep(self, attempt: int) -> None:
        time.sleep(self.backoff_factor ** attempt)

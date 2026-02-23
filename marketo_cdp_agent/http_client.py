from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass
class HttpRequestError(RuntimeError):
    message: str
    status_code: int | None = None
    response_body: str | None = None

    def __str__(self) -> str:
        if self.status_code is None:
            return self.message
        return f"{self.message} (status={self.status_code}, body={self.response_body})"


class JsonHttpClient:
    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | list[Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        final_url = _with_query(url, params)
        request_headers = dict(headers or {})
        payload: bytes | None = None

        if body is not None:
            payload = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        request = Request(final_url, data=payload, headers=request_headers, method=method.upper())
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                if not raw.strip():
                    return {}
                parsed = json.loads(raw)
                if not isinstance(parsed, dict):
                    raise HttpRequestError("Expected JSON object response from upstream endpoint")
                return parsed
        except HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise HttpRequestError(
                "HTTP request failed",
                status_code=exc.code,
                response_body=body_text,
            ) from exc
        except URLError as exc:
            raise HttpRequestError(f"Network request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise HttpRequestError("Received invalid JSON response") from exc


def _with_query(url: str, params: dict[str, Any] | None) -> str:
    if not params:
        return url
    filtered = {k: v for k, v in params.items() if v is not None}
    return f"{url}?{urlencode(filtered, doseq=True)}"

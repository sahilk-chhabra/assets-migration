from __future__ import annotations

from typing import Any

from marketo_cdp_agent.config import CdpConfig
from marketo_cdp_agent.http_client import JsonHttpClient


class CdpClient:
    def __init__(self, config: CdpConfig, http_client: JsonHttpClient | None = None) -> None:
        self.config = config
        self.http_client = http_client or JsonHttpClient()

    def upsert_profiles(self, profiles: list[dict[str, Any]]) -> dict[str, Any]:
        if not profiles:
            return {"accepted": 0}

        endpoint = self.config.endpoints.get("upsert_profiles", self.config.ingestion_path)
        url = f"{self.config.base_url}{endpoint}"
        payload = self.http_client.request_json(
            "POST",
            url,
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Accept": "application/json",
            },
            body={
                "source": self.config.source_name,
                "profiles": profiles,
            },
        )
        return payload

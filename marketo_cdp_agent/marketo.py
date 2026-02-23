from __future__ import annotations

from typing import Any

from marketo_cdp_agent.config import MarketoConfig
from marketo_cdp_agent.http_client import JsonHttpClient
from marketo_cdp_agent.models import LeadRecord


class MarketoClient:
    def __init__(self, config: MarketoConfig, http_client: JsonHttpClient | None = None) -> None:
        self.config = config
        self.http_client = http_client or JsonHttpClient()
        self._access_token: str | None = None

    def get_leads_by_ids(self, lead_ids: set[str]) -> list[LeadRecord]:
        if not lead_ids:
            return []

        token = self._ensure_access_token()
        endpoint = self.config.endpoints.get("list_leads", "/v1/leads.json")
        url = f"{self.config.rest_base_url}{endpoint}"

        records: dict[str, LeadRecord] = {}
        batch_size = max(1, min(self.config.batch_size, 300))
        sorted_ids = sorted(lead_ids)
        for idx in range(0, len(sorted_ids), batch_size):
            chunk = sorted_ids[idx : idx + batch_size]
            payload = self.http_client.request_json(
                "GET",
                url,
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "filterType": "id",
                    "filterValues": ",".join(chunk),
                    "fields": ",".join(self.config.fields),
                },
            )
            if payload.get("success") is False:
                errors = payload.get("errors") or []
                raise RuntimeError(f"Marketo lead lookup failed: {errors}")

            for item in payload.get("result", []):
                lead = _to_lead_record(item)
                records[lead.lead_id] = lead
        return [records[lead_id] for lead_id in sorted(records)]

    def _ensure_access_token(self) -> str:
        if self._access_token:
            return self._access_token

        endpoint = self.config.endpoints.get("identity_token", "/identity/oauth/token")
        url = f"{self.config.identity_url}{endpoint}"
        payload = self.http_client.request_json(
            "GET",
            url,
            params={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            },
        )
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Marketo identity endpoint did not return access_token")
        self._access_token = str(token)
        return self._access_token


def _to_lead_record(item: dict[str, Any]) -> LeadRecord:
    lead_id = str(item.get("id", "")).strip()
    if not lead_id:
        raise ValueError("Marketo lead payload missing id")
    return LeadRecord(
        lead_id=lead_id,
        email=_as_optional_string(item.get("email")),
        first_name=_as_optional_string(item.get("firstName")),
        last_name=_as_optional_string(item.get("lastName")),
        company=_as_optional_string(item.get("company")),
        title=_as_optional_string(item.get("title")),
        phone=_as_optional_string(item.get("phone")),
        updated_at=_as_optional_string(item.get("updatedAt")),
        raw=dict(item),
    )


def _as_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

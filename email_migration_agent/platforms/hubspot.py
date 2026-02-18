from __future__ import annotations

from typing import Any

from email_migration_agent.config import HubSpotConfig
from email_migration_agent.http_client import ApiError, HttpClient
from email_migration_agent.models import EmailTemplate, TemplateSummary
from email_migration_agent.platforms.base import PlatformClient


class HubSpotClient(PlatformClient):
    DEFAULT_ENDPOINTS = {
        "list_templates": "/marketing/v3/emails",
        "get_template_by_id": "/marketing/v3/emails/{id}",
        "search_templates": "/marketing/v3/emails/search",
        "create_template": "/marketing/v3/emails",
        "update_template": "/marketing/v3/emails/{id}",
    }

    def __init__(self, config: HubSpotConfig, http_client: HttpClient | None = None):
        self.config = config
        self.http = http_client or HttpClient()

    def list_templates(self) -> list[TemplateSummary]:
        path = self._endpoint("list_templates")
        after: str | None = None
        items: list[TemplateSummary] = []

        while True:
            params: dict[str, Any] = {"limit": 100}
            if after:
                params["after"] = after
            payload = self._request("GET", path, params=params)

            rows = []
            if isinstance(payload, dict):
                maybe_rows = payload.get("results")
                if isinstance(maybe_rows, list):
                    rows = [row for row in maybe_rows if isinstance(row, dict)]

            for row in rows:
                template_id = self._extract_id(row)
                if not template_id:
                    continue
                name = (
                    row.get("name")
                    or row.get("emailName")
                    or row.get("subject")
                    or f"hubspot-template-{template_id}"
                )
                items.append(TemplateSummary(template_id=template_id, name=str(name), raw=row))

            after = self._extract_next_after(payload)
            if not after:
                break

        return items

    def get_template(self, template_id: str) -> EmailTemplate:
        path = self._endpoint("get_template_by_id").format(id=template_id)
        payload = self._request("GET", path)
        if not isinstance(payload, dict):
            raise ApiError(
                status_code=None,
                message=f"Unexpected HubSpot template response for id={template_id}",
                url=self._url(path),
                response_body=str(payload),
            )

        name = payload.get("name") or payload.get("emailName") or f"hubspot-template-{template_id}"
        subject = payload.get("subject")
        html = self._extract_html(payload)
        text = self._extract_text(payload)

        return EmailTemplate(
            source_id=self._extract_id(payload) or template_id,
            name=str(name),
            subject=str(subject) if subject is not None else None,
            html=html,
            text=text,
            metadata={"hubspot_details": payload},
        )

    def upsert_template(self, template: EmailTemplate) -> str:
        existing = self._find_by_name(template.name)
        payload = self._build_payload(template)
        if existing:
            template_id = self._extract_id(existing)
            if not template_id:
                raise ApiError(
                    status_code=None,
                    message=f"Unable to determine destination id for template '{template.name}'",
                    url=self._url(self._endpoint("search_templates")),
                    response_body=str(existing),
                )
            update_path = self._endpoint("update_template").format(id=template_id)
            self._request("PATCH", update_path, json_body=payload)
            return template_id

        create_path = self._endpoint("create_template")
        created = self._request("POST", create_path, json_body=payload)
        created_id = self._extract_id(created)
        if not created_id:
            raise ApiError(
                status_code=None,
                message=f"HubSpot create response missing id for template '{template.name}'",
                url=self._url(create_path),
                response_body=str(created),
            )
        return created_id

    def _find_by_name(self, name: str) -> dict[str, Any] | None:
        search_path = self._endpoint("search_templates")
        query = {"query": name, "limit": 20}
        try:
            payload = self._request("POST", search_path, json_body=query)
            rows = []
            if isinstance(payload, dict):
                maybe_rows = payload.get("results")
                if isinstance(maybe_rows, list):
                    rows = [row for row in maybe_rows if isinstance(row, dict)]
            for row in rows:
                row_name = str(row.get("name") or row.get("emailName") or "")
                if row_name.lower() == name.lower():
                    return row
        except ApiError as exc:
            # Some portals do not have this endpoint/API scope. Fallback to list+scan.
            if exc.status_code not in {400, 404, 405}:
                raise

        for summary in self.list_templates():
            if summary.name.lower() == name.lower():
                return summary.raw
        return None

    @staticmethod
    def _build_payload(template: EmailTemplate) -> dict[str, Any]:
        subject = template.subject or ""
        text = template.text or ""
        # Keep both flattened and nested forms to maximize compatibility
        # with different HubSpot email/template API variants.
        payload: dict[str, Any] = {
            "name": template.name,
            "subject": subject,
            "html": template.html,
            "plainText": text,
            "content": {"html": template.html, "plainText": text},
        }
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any] | list[Any] | str | None:
        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Accept": "application/json",
        }
        return self.http.request(
            method,
            self._url(path),
            headers=headers,
            params=params,
            json_body=json_body,
        )

    def _endpoint(self, key: str) -> str:
        return self.config.endpoints.get(key, self.DEFAULT_ENDPOINTS[key])

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.config.base_url}{path}"

    @staticmethod
    def _extract_next_after(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        paging = payload.get("paging")
        if not isinstance(paging, dict):
            return None
        next_page = paging.get("next")
        if not isinstance(next_page, dict):
            return None
        after = next_page.get("after")
        return str(after) if after is not None else None

    @staticmethod
    def _extract_id(payload: Any) -> str | None:
        if isinstance(payload, dict):
            for key in ("id", "templateId", "emailId"):
                if payload.get(key) is not None:
                    return str(payload[key])
        return None

    @staticmethod
    def _extract_html(payload: dict[str, Any]) -> str:
        for key in ("html", "body", "htmlContent"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value

        content = payload.get("content")
        if isinstance(content, dict):
            for key in ("html", "body", "htmlContent"):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return ""

    @staticmethod
    def _extract_text(payload: dict[str, Any]) -> str | None:
        for key in ("plainText", "text", "textContent"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        content = payload.get("content")
        if isinstance(content, dict):
            for key in ("plainText", "text", "textContent"):
                value = content.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return None

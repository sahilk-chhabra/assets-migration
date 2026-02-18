from __future__ import annotations

import time
from typing import Any

from email_migration_agent.config import MarketoConfig
from email_migration_agent.http_client import ApiError, HttpClient
from email_migration_agent.models import EmailTemplate, TemplateSummary
from email_migration_agent.platforms.base import PlatformClient


class MarketoClient(PlatformClient):
    DEFAULT_ENDPOINTS = {
        "list_templates": "/asset/v1/emailTemplates.json",
        "get_template_by_id": "/asset/v1/emailTemplate/{id}.json",
        "get_template_content": "/asset/v1/emailTemplate/{id}/content.json",
        "find_by_name": "/asset/v1/emailTemplate/byName.json",
        "create_template": "/asset/v1/emailTemplates.json",
        "update_template_content": "/asset/v1/emailTemplate/{id}/content.json",
    }

    def __init__(self, config: MarketoConfig, http_client: HttpClient | None = None):
        self.config = config
        self.http = http_client or HttpClient()
        self._token: str | None = None
        self._token_expiry_epoch: float = 0.0

    def list_templates(self) -> list[TemplateSummary]:
        path = self._endpoint("list_templates")
        all_items: list[TemplateSummary] = []
        offset = 0
        max_return = 200

        while True:
            payload = self._request(
                "GET",
                path,
                params={"offset": offset, "maxReturn": max_return},
            )
            rows = self._extract_result_list(payload)
            if not rows:
                break

            for row in rows:
                template_id = str(row.get("id", "")).strip()
                if not template_id:
                    continue
                all_items.append(
                    TemplateSummary(
                        template_id=template_id,
                        name=row.get("name", f"marketo-template-{template_id}"),
                        raw=row,
                    )
                )

            if len(rows) < max_return:
                break
            offset += max_return

        return all_items

    def get_template(self, template_id: str) -> EmailTemplate:
        details_path = self._endpoint("get_template_by_id").format(id=template_id)
        content_path = self._endpoint("get_template_content").format(id=template_id)

        details_response = self._request("GET", details_path)
        content_response = self._request("GET", content_path)

        details = self._extract_first_result(details_response)
        content_rows = self._extract_result_list(content_response)

        html_parts: list[str] = []
        text_parts: list[str] = []
        subject = details.get("subject")
        for row in content_rows:
            row_type = str(row.get("type", "")).lower()
            value = row.get("value")
            if value is None:
                continue
            value_text = str(value)
            if "subject" in row_type and not subject:
                subject = value_text
            elif "text" in row_type:
                text_parts.append(value_text)
            else:
                html_parts.append(value_text)

        html = "\n".join(part for part in html_parts if part.strip())
        text = "\n".join(part for part in text_parts if part.strip()) or None
        if not html:
            html = str(details.get("html") or details.get("content") or "")

        return EmailTemplate(
            source_id=str(details.get("id", template_id)),
            name=details.get("name", f"marketo-template-{template_id}"),
            subject=subject,
            html=html,
            text=text,
            metadata={"marketo_details": details, "marketo_content": content_rows},
        )

    def upsert_template(self, template: EmailTemplate) -> str:
        existing = self._find_by_name(template.name)
        if existing:
            template_id = str(existing.get("id"))
        else:
            template_id = self._create_template(template)

        self._update_template_content(template_id, template)
        return template_id

    def _find_by_name(self, name: str) -> dict[str, Any] | None:
        path = self._endpoint("find_by_name")
        try:
            response = self._request("GET", path, params={"name": name})
        except ApiError as exc:
            # If by-name endpoint isn't available for this account/API level,
            # gracefully fallback to scanning list results.
            if exc.status_code in {400, 404, 405}:
                matches = [row for row in self.list_templates() if row.name == name]
                if not matches:
                    return None
                return matches[0].raw
            raise

        row = self._extract_first_result(response)
        return row if row else None

    def _create_template(self, template: EmailTemplate) -> str:
        path = self._endpoint("create_template")
        payload: dict[str, Any] = {"name": template.name}
        if self.config.folder_id is not None:
            payload["folder"] = {"id": self.config.folder_id, "type": self.config.folder_type}
        if template.subject:
            payload["subject"] = template.subject

        response = self._request("POST", path, json_body=payload)
        created = self._extract_first_result(response)
        created_id = created.get("id")
        if not created_id:
            raise ApiError(
                status_code=None,
                message=f"Marketo create response missing template id for '{template.name}'",
                url=self._url(path),
            )
        return str(created_id)

    def _update_template_content(self, template_id: str, template: EmailTemplate) -> None:
        path = self._endpoint("update_template_content").format(id=template_id)
        payload_candidates = [
            {"html": template.html, "text": template.text, "subject": template.subject},
            {"content": template.html, "subject": template.subject, "text": template.text},
            {"type": "HTML", "value": template.html},
        ]
        last_error: ApiError | None = None

        for payload in payload_candidates:
            compact = {k: v for k, v in payload.items() if v is not None}
            if not compact:
                continue
            try:
                self._request("POST", path, json_body=compact)
                return
            except ApiError as exc:
                last_error = exc
                continue

        if last_error is not None:
            raise ApiError(
                status_code=last_error.status_code,
                message=f"Unable to update Marketo template content for id={template_id}",
                url=last_error.url,
                response_body=last_error.response_body,
            ) from last_error

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
    ) -> dict[str, Any] | list[Any] | str | None:
        url = self._url(path)
        auth_params = dict(params or {})
        auth_params["access_token"] = self._get_access_token()
        response = self.http.request(
            method,
            url,
            params=auth_params,
            json_body=json_body,
        )
        self._assert_success(response, url)
        return response

    def _get_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expiry_epoch:
            return self._token

        token_url = f"{self.config.identity_url}/oauth/token"
        token_response = self.http.request(
            "GET",
            token_url,
            params={
                "grant_type": "client_credentials",
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
            },
        )
        if not isinstance(token_response, dict):
            raise ApiError(
                status_code=None,
                message="Unexpected token response shape from Marketo",
                url=token_url,
                response_body=str(token_response),
            )

        access_token = token_response.get("access_token")
        if not access_token:
            raise ApiError(
                status_code=None,
                message="Marketo token response did not contain access_token",
                url=token_url,
                response_body=str(token_response),
            )

        expires_in = int(token_response.get("expires_in", 300))
        self._token = str(access_token)
        self._token_expiry_epoch = now + max(expires_in - 30, 60)
        return self._token

    def _endpoint(self, key: str) -> str:
        return self.config.endpoints.get(key, self.DEFAULT_ENDPOINTS[key])

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.config.rest_base_url}{path}"

    @staticmethod
    def _assert_success(response: Any, url: str) -> None:
        if not isinstance(response, dict):
            return
        if response.get("success", True):
            return
        errors = response.get("errors") or response.get("error")
        raise ApiError(status_code=None, message=f"Marketo API error: {errors}", url=url, response_body=str(response))

    @staticmethod
    def _extract_result_list(response: Any) -> list[dict[str, Any]]:
        if isinstance(response, dict):
            result = response.get("result")
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict)]
        return []

    def _extract_first_result(self, response: Any) -> dict[str, Any]:
        rows = self._extract_result_list(response)
        return rows[0] if rows else {}

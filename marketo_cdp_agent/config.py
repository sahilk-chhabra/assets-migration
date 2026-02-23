from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
DEFAULT_MARKETO_FIELDS = [
    "id",
    "email",
    "firstName",
    "lastName",
    "company",
    "title",
    "phone",
    "updatedAt",
]


@dataclass
class MarketoConfig:
    identity_url: str
    rest_base_url: str
    client_id: str
    client_secret: str
    batch_size: int = 300
    fields: list[str] = field(default_factory=lambda: list(DEFAULT_MARKETO_FIELDS))
    endpoints: dict[str, str] = field(default_factory=dict)


@dataclass
class CdpConfig:
    base_url: str
    api_key: str
    ingestion_path: str = "/v1/profiles/upsert"
    batch_size: int = 100
    source_name: str = "marketo"
    endpoints: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentConfig:
    marketo: MarketoConfig
    cdp: CdpConfig


def load_config(path: str) -> AgentConfig:
    with open(path, "r", encoding="utf-8") as file_obj:
        raw = json.load(file_obj)

    resolved = _resolve_env(raw)
    marketo_raw = resolved.get("marketo", {})
    cdp_raw = resolved.get("cdp", {})

    missing: list[str] = []
    for key in ("identity_url", "rest_base_url", "client_id", "client_secret"):
        if not marketo_raw.get(key):
            missing.append(f"marketo.{key}")
    for key in ("base_url", "api_key"):
        if not cdp_raw.get(key):
            missing.append(f"cdp.{key}")
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required config values: {joined}")

    marketo = MarketoConfig(
        identity_url=str(marketo_raw["identity_url"]).rstrip("/"),
        rest_base_url=str(marketo_raw["rest_base_url"]).rstrip("/"),
        client_id=str(marketo_raw["client_id"]),
        client_secret=str(marketo_raw["client_secret"]),
        batch_size=int(marketo_raw.get("batch_size", 300)),
        fields=[str(item) for item in marketo_raw.get("fields", [])] or list(DEFAULT_MARKETO_FIELDS),
        endpoints=dict(marketo_raw.get("endpoints", {})),
    )
    cdp = CdpConfig(
        base_url=str(cdp_raw["base_url"]).rstrip("/"),
        api_key=str(cdp_raw["api_key"]),
        ingestion_path=str(cdp_raw.get("ingestion_path", "/v1/profiles/upsert")),
        batch_size=int(cdp_raw.get("batch_size", 100)),
        source_name=str(cdp_raw.get("source_name", "marketo")),
        endpoints=dict(cdp_raw.get("endpoints", {})),
    )
    return AgentConfig(marketo=marketo, cdp=cdp)


def _resolve_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), match.group(0)), value)
    return value

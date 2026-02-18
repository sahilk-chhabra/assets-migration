from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


@dataclass
class MarketoConfig:
    identity_url: str
    rest_base_url: str
    client_id: str
    client_secret: str
    folder_id: str | int | None = None
    folder_type: str = "Folder"
    endpoints: dict[str, str] = field(default_factory=dict)


@dataclass
class HubSpotConfig:
    access_token: str
    base_url: str = "https://api.hubapi.com"
    folder_path: str | None = None
    endpoints: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentConfig:
    marketo: MarketoConfig
    hubspot: HubSpotConfig


def load_config(path: str) -> AgentConfig:
    with open(path, "r", encoding="utf-8") as file_obj:
        raw = json.load(file_obj)

    resolved = _resolve_env(raw)
    marketo_raw = resolved.get("marketo", {})
    hubspot_raw = resolved.get("hubspot", {})

    missing = []
    for key in ("identity_url", "rest_base_url", "client_id", "client_secret"):
        if not marketo_raw.get(key):
            missing.append(f"marketo.{key}")
    if not hubspot_raw.get("access_token"):
        missing.append("hubspot.access_token")
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"Missing required config values: {joined}")

    marketo = MarketoConfig(
        identity_url=marketo_raw["identity_url"].rstrip("/"),
        rest_base_url=marketo_raw["rest_base_url"].rstrip("/"),
        client_id=marketo_raw["client_id"],
        client_secret=marketo_raw["client_secret"],
        folder_id=marketo_raw.get("folder_id"),
        folder_type=marketo_raw.get("folder_type", "Folder"),
        endpoints=dict(marketo_raw.get("endpoints", {})),
    )
    hubspot = HubSpotConfig(
        access_token=hubspot_raw["access_token"],
        base_url=hubspot_raw.get("base_url", "https://api.hubapi.com").rstrip("/"),
        folder_path=hubspot_raw.get("folder_path"),
        endpoints=dict(hubspot_raw.get("endpoints", {})),
    )
    return AgentConfig(marketo=marketo, hubspot=hubspot)


def _resolve_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda m: os.getenv(m.group(1), m.group(0)), value)
    return value

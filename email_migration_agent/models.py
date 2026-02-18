from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TemplateSummary:
    """Minimal template metadata used for selection."""

    template_id: str
    name: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailTemplate:
    """Platform-neutral representation of an email template."""

    source_id: str
    name: str
    subject: str | None
    html: str
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MigrationResult:
    """Result for one template migration attempt."""

    source_id: str
    source_name: str
    destination_id: str | None
    status: str
    message: str

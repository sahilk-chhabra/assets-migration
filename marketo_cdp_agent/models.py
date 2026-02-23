from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LeadSummary:
    lead_id: str
    email: str | None
    name: str


@dataclass
class LeadRecord:
    lead_id: str
    email: str | None
    first_name: str | None
    last_name: str | None
    company: str | None
    title: str | None
    phone: str | None
    updated_at: str | None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        first = (self.first_name or "").strip()
        last = (self.last_name or "").strip()
        name = " ".join(part for part in (first, last) if part)
        return name or (self.email or self.lead_id)

    def to_summary(self) -> LeadSummary:
        return LeadSummary(lead_id=self.lead_id, email=self.email, name=self.display_name)


@dataclass(frozen=True)
class MigrationResult:
    lead_id: str
    lead_name: str
    status: str
    destination_id: str | None
    message: str

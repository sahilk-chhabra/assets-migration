from __future__ import annotations

from abc import ABC, abstractmethod

from email_migration_agent.models import EmailTemplate, TemplateSummary


class PlatformClient(ABC):
    @abstractmethod
    def list_templates(self) -> list[TemplateSummary]:
        """Return all available templates for selection."""

    @abstractmethod
    def get_template(self, template_id: str) -> EmailTemplate:
        """Return a full template payload."""

    @abstractmethod
    def upsert_template(self, template: EmailTemplate) -> str:
        """Create or update destination template and return destination ID."""

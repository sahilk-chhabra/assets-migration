from __future__ import annotations

from datetime import datetime, timezone

from email_migration_agent.models import EmailTemplate, MigrationResult, TemplateSummary
from email_migration_agent.platforms.base import PlatformClient


class MigrationAgent:
    """Coordinates fetching from one platform and writing to another."""

    def __init__(
        self,
        source_client: PlatformClient,
        destination_client: PlatformClient,
        *,
        source_label: str,
        destination_label: str,
        target_name_prefix: str | None = None,
    ) -> None:
        self.source_client = source_client
        self.destination_client = destination_client
        self.source_label = source_label
        self.destination_label = destination_label
        self.target_name_prefix = target_name_prefix

    def migrate(
        self,
        selected_templates: list[TemplateSummary],
        *,
        dry_run: bool = False,
    ) -> list[MigrationResult]:
        results: list[MigrationResult] = []
        for summary in selected_templates:
            source_id = summary.template_id
            source_name = summary.name
            try:
                full_template = self.source_client.get_template(source_id)
                outbound = self._prepare_template(full_template)

                if dry_run:
                    results.append(
                        MigrationResult(
                            source_id=source_id,
                            source_name=source_name,
                            destination_id=None,
                            status="dry_run",
                            message=(
                                f"Prepared '{outbound.name}' for migration "
                                f"{self.source_label} -> {self.destination_label}"
                            ),
                        )
                    )
                    continue

                destination_id = self.destination_client.upsert_template(outbound)
                results.append(
                    MigrationResult(
                        source_id=source_id,
                        source_name=source_name,
                        destination_id=destination_id,
                        status="migrated",
                        message=(
                            f"Migrated '{source_name}' from {self.source_label} "
                            f"to {self.destination_label} as id={destination_id}"
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - intentionally catch per-template errors
                results.append(
                    MigrationResult(
                        source_id=source_id,
                        source_name=source_name,
                        destination_id=None,
                        status="failed",
                        message=str(exc),
                    )
                )
        return results

    def _prepare_template(self, template: EmailTemplate) -> EmailTemplate:
        name = template.name
        if self.target_name_prefix:
            name = f"{self.target_name_prefix}{name}"

        metadata = dict(template.metadata)
        metadata["migration"] = {
            "source_platform": self.source_label,
            "destination_platform": self.destination_label,
            "source_template_id": template.source_id,
            "migrated_at": datetime.now(timezone.utc).isoformat(),
        }

        return EmailTemplate(
            source_id=template.source_id,
            name=name,
            subject=template.subject,
            html=template.html,
            text=template.text,
            metadata=metadata,
        )

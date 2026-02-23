from __future__ import annotations

from marketo_cdp_agent.cdp import CdpClient
from marketo_cdp_agent.models import LeadRecord, MigrationResult


class MarketoCdpMigrationAgent:
    """Coordinates lead transformation and CDP ingestion."""

    def __init__(self, cdp_client: CdpClient, *, batch_size: int = 100) -> None:
        self.cdp_client = cdp_client
        self.batch_size = max(1, batch_size)

    def migrate(self, leads: list[LeadRecord], *, dry_run: bool = False) -> list[MigrationResult]:
        if dry_run:
            return [
                MigrationResult(
                    lead_id=lead.lead_id,
                    lead_name=lead.display_name,
                    status="dry_run",
                    destination_id=None,
                    message=f"Prepared lead {lead.lead_id} for CDP ingestion",
                )
                for lead in leads
            ]

        results: list[MigrationResult] = []
        for batch in _chunk(leads, self.batch_size):
            profiles = [self.lead_to_profile(lead) for lead in batch]
            try:
                response = self.cdp_client.upsert_profiles(profiles)
                destination_prefix = str(response.get("batch_id") or "cdp")
                for idx, lead in enumerate(batch):
                    results.append(
                        MigrationResult(
                            lead_id=lead.lead_id,
                            lead_name=lead.display_name,
                            status="migrated",
                            destination_id=f"{destination_prefix}:{idx}",
                            message="Lead ingested into CDP",
                        )
                    )
            except Exception as exc:  # noqa: BLE001 - preserve per-lead failures
                for lead in batch:
                    results.append(
                        MigrationResult(
                            lead_id=lead.lead_id,
                            lead_name=lead.display_name,
                            status="failed",
                            destination_id=None,
                            message=str(exc),
                        )
                    )
        return results

    @staticmethod
    def lead_to_profile(lead: LeadRecord) -> dict[str, object | None]:
        return {
            "external_id": lead.lead_id,
            "email": lead.email,
            "traits": {
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "company": lead.company,
                "title": lead.title,
                "phone": lead.phone,
                "updated_at": lead.updated_at,
            },
        }


def _chunk(items: list[LeadRecord], size: int) -> list[list[LeadRecord]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]

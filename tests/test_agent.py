from __future__ import annotations

import unittest

from marketo_cdp_agent.agent import MarketoCdpMigrationAgent
from marketo_cdp_agent.models import LeadRecord


class FakeCdpClient:
    def __init__(self, *, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls = 0
        self.received_batches: list[list[dict[str, object | None]]] = []

    def upsert_profiles(self, profiles: list[dict[str, object | None]]) -> dict[str, object]:
        self.calls += 1
        if self.fail_on_call == self.calls:
            raise RuntimeError("cdp ingestion failed")
        self.received_batches.append(profiles)
        return {"batch_id": f"batch-{self.calls}"}


class MigrationAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.leads = [
            LeadRecord(
                lead_id="1",
                email="a@example.com",
                first_name="Alice",
                last_name="A",
                company=None,
                title=None,
                phone=None,
                updated_at=None,
            ),
            LeadRecord(
                lead_id="2",
                email="b@example.com",
                first_name="Bob",
                last_name="B",
                company=None,
                title=None,
                phone=None,
                updated_at=None,
            ),
            LeadRecord(
                lead_id="3",
                email="c@example.com",
                first_name="Carol",
                last_name="C",
                company=None,
                title=None,
                phone=None,
                updated_at=None,
            ),
        ]

    def test_dry_run_does_not_write(self) -> None:
        cdp = FakeCdpClient()
        agent = MarketoCdpMigrationAgent(cdp, batch_size=2)
        results = agent.migrate(self.leads[:1], dry_run=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "dry_run")
        self.assertEqual(cdp.received_batches, [])

    def test_migrate_success_and_batches(self) -> None:
        cdp = FakeCdpClient()
        agent = MarketoCdpMigrationAgent(cdp, batch_size=2)
        results = agent.migrate(self.leads, dry_run=False)
        self.assertEqual([row.status for row in results], ["migrated", "migrated", "migrated"])
        self.assertEqual(len(cdp.received_batches), 2)
        self.assertEqual(len(cdp.received_batches[0]), 2)
        self.assertEqual(len(cdp.received_batches[1]), 1)

    def test_migrate_handles_batch_failure(self) -> None:
        cdp = FakeCdpClient(fail_on_call=2)
        agent = MarketoCdpMigrationAgent(cdp, batch_size=2)
        results = agent.migrate(self.leads, dry_run=False)
        self.assertEqual([row.status for row in results], ["migrated", "migrated", "failed"])

    def test_lead_to_profile_mapping(self) -> None:
        profile = MarketoCdpMigrationAgent.lead_to_profile(self.leads[0])
        self.assertEqual(profile["external_id"], "1")
        self.assertEqual(profile["email"], "a@example.com")
        self.assertEqual(profile["traits"]["first_name"], "Alice")


if __name__ == "__main__":
    unittest.main()

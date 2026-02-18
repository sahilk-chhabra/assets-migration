from __future__ import annotations

import unittest

from email_migration_agent.agent import MigrationAgent
from email_migration_agent.models import EmailTemplate, TemplateSummary
from email_migration_agent.platforms.base import PlatformClient


class FakeSource(PlatformClient):
    def __init__(self, fail_on: str | None = None):
        self.fail_on = fail_on

    def list_templates(self):
        return [
            TemplateSummary(template_id="1", name="Welcome"),
            TemplateSummary(template_id="2", name="Promo"),
        ]

    def get_template(self, template_id: str):
        if self.fail_on == template_id:
            raise RuntimeError("source lookup failed")
        return EmailTemplate(
            source_id=template_id,
            name=f"template-{template_id}",
            subject=f"subject-{template_id}",
            html=f"<h1>{template_id}</h1>",
            text=f"text-{template_id}",
        )

    def upsert_template(self, template: EmailTemplate):
        raise NotImplementedError


class FakeDestination(PlatformClient):
    def __init__(self):
        self.saved: list[EmailTemplate] = []

    def list_templates(self):
        return []

    def get_template(self, template_id: str):
        raise NotImplementedError

    def upsert_template(self, template: EmailTemplate):
        self.saved.append(template)
        return f"dest-{template.source_id}"


class MigrationAgentTests(unittest.TestCase):
    def test_dry_run_does_not_write(self):
        source = FakeSource()
        destination = FakeDestination()
        agent = MigrationAgent(
            source,
            destination,
            source_label="marketo",
            destination_label="hubspot",
            target_name_prefix="mkto-",
        )
        selected = [TemplateSummary(template_id="1", name="Welcome")]
        results = agent.migrate(selected, dry_run=True)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "dry_run")
        self.assertEqual(destination.saved, [])

    def test_migrate_success(self):
        source = FakeSource()
        destination = FakeDestination()
        agent = MigrationAgent(
            source,
            destination,
            source_label="hubspot",
            destination_label="marketo",
            target_name_prefix="hs-",
        )
        selected = [TemplateSummary(template_id="2", name="Promo")]
        results = agent.migrate(selected, dry_run=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "migrated")
        self.assertEqual(results[0].destination_id, "dest-2")
        self.assertEqual(destination.saved[0].name, "hs-template-2")

    def test_migrate_handles_per_template_error(self):
        source = FakeSource(fail_on="2")
        destination = FakeDestination()
        agent = MigrationAgent(
            source,
            destination,
            source_label="hubspot",
            destination_label="marketo",
        )
        selected = [
            TemplateSummary(template_id="1", name="Welcome"),
            TemplateSummary(template_id="2", name="Promo"),
        ]
        results = agent.migrate(selected, dry_run=False)
        statuses = [row.status for row in results]
        self.assertEqual(statuses, ["migrated", "failed"])


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import tempfile
import unittest

from marketo_cdp_agent.models import LeadSummary
from marketo_cdp_agent.selection import (
    SelectionCriteria,
    load_selection_file,
    merge_criteria,
    parse_lead_ids,
    select_leads,
)


class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.available = [
            LeadSummary(lead_id="1", email="alice@example.com", name="Alice"),
            LeadSummary(lead_id="2", email="bob@company.com", name="Bob"),
            LeadSummary(lead_id="3", email="carol@example.com", name="Carol"),
        ]

    def test_parse_lead_ids(self) -> None:
        parsed = parse_lead_ids("1, 2 ,3,,")
        self.assertEqual(parsed, {"1", "2", "3"})

    def test_merge_criteria(self) -> None:
        cli = SelectionCriteria(lead_ids={"1"}, email_contains=None)
        file_criteria = SelectionCriteria(lead_ids={"2"}, email_contains="@example.com")
        merged = merge_criteria(cli.lead_ids, cli.email_contains, file_criteria)
        self.assertEqual(merged.lead_ids, {"1", "2"})
        self.assertEqual(merged.email_contains, "@example.com")

    def test_select_leads_by_ids_and_email_filter(self) -> None:
        criteria = SelectionCriteria(lead_ids={"1", "2", "3"}, email_contains="@example.com")
        selected = select_leads(self.available, criteria)
        self.assertEqual([row.lead_id for row in selected], ["1", "3"])

    def test_select_leads_strict_missing_ids(self) -> None:
        criteria = SelectionCriteria(lead_ids={"999"}, email_contains=None)
        with self.assertRaisesRegex(ValueError, "Lead IDs not found"):
            select_leads(self.available, criteria, strict_ids=True)

    def test_load_selection_file_list(self) -> None:
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as file_obj:
            json.dump(["1", "2"], file_obj)
            file_obj.flush()
            criteria = load_selection_file(file_obj.name)
        self.assertEqual(criteria.lead_ids, {"1", "2"})

    def test_load_selection_file_object(self) -> None:
        payload = {"lead_ids": ["1", "3"], "email_contains": "@example.com"}
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as file_obj:
            json.dump(payload, file_obj)
            file_obj.flush()
            criteria = load_selection_file(file_obj.name)
        self.assertEqual(criteria.lead_ids, {"1", "3"})
        self.assertEqual(criteria.email_contains, "@example.com")


if __name__ == "__main__":
    unittest.main()

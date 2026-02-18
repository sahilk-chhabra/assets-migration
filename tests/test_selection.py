from __future__ import annotations

import json
import tempfile
import unittest

from email_migration_agent.models import TemplateSummary
from email_migration_agent.selection import (
    SelectionCriteria,
    load_selection_file,
    merge_criteria,
    parse_template_ids,
    select_templates,
)


class SelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.available = [
            TemplateSummary(template_id="1", name="Welcome Email"),
            TemplateSummary(template_id="2", name="Monthly Newsletter"),
            TemplateSummary(template_id="3", name="Promo - Winter"),
        ]

    def test_parse_template_ids(self) -> None:
        parsed = parse_template_ids("1, 2 ,3,,")
        self.assertEqual(parsed, {"1", "2", "3"})

    def test_merge_criteria(self) -> None:
        cli = SelectionCriteria(template_ids={"1"}, name_contains=None)
        file_criteria = SelectionCriteria(template_ids={"2"}, name_contains="promo")
        merged = merge_criteria(cli.template_ids, cli.name_contains, file_criteria)
        self.assertEqual(merged.template_ids, {"1", "2"})
        self.assertEqual(merged.name_contains, "promo")

    def test_select_templates_by_ids_and_name_filter(self) -> None:
        criteria = SelectionCriteria(template_ids={"1", "2", "3"}, name_contains="newsletter")
        selected = select_templates(self.available, criteria)
        self.assertEqual([row.template_id for row in selected], ["2"])

    def test_select_templates_strict_missing_ids(self) -> None:
        criteria = SelectionCriteria(template_ids={"999"}, name_contains=None)
        with self.assertRaisesRegex(ValueError, "Template IDs not found"):
            select_templates(self.available, criteria, strict_ids=True)

    def test_load_selection_file_list(self) -> None:
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as file_obj:
            json.dump(["1", "2"], file_obj)
            file_obj.flush()
            criteria = load_selection_file(file_obj.name)
        self.assertEqual(criteria.template_ids, {"1", "2"})

    def test_load_selection_file_object(self) -> None:
        payload = {"template_ids": ["1", "3"], "name_contains": "Promo"}
        with tempfile.NamedTemporaryFile("w+", suffix=".json") as file_obj:
            json.dump(payload, file_obj)
            file_obj.flush()
            criteria = load_selection_file(file_obj.name)
        self.assertEqual(criteria.template_ids, {"1", "3"})
        self.assertEqual(criteria.name_contains, "Promo")


if __name__ == "__main__":
    unittest.main()

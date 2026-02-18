from __future__ import annotations

import json
from dataclasses import dataclass

from email_migration_agent.models import TemplateSummary


@dataclass(frozen=True)
class SelectionCriteria:
    template_ids: set[str]
    name_contains: str | None = None


def parse_template_ids(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {chunk.strip() for chunk in raw.split(",") if chunk.strip()}


def load_selection_file(path: str) -> SelectionCriteria:
    with open(path, "r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    if isinstance(payload, list):
        ids = {str(item).strip() for item in payload if str(item).strip()}
        return SelectionCriteria(template_ids=ids, name_contains=None)

    if isinstance(payload, dict):
        ids_raw = payload.get("template_ids") or payload.get("ids") or []
        ids = {str(item).strip() for item in ids_raw if str(item).strip()}
        name_contains = payload.get("name_contains")
        if name_contains is not None and not isinstance(name_contains, str):
            raise ValueError("selection file field 'name_contains' must be a string")
        return SelectionCriteria(template_ids=ids, name_contains=name_contains)

    raise ValueError("selection file must be a JSON array or object")


def merge_criteria(
    cli_template_ids: set[str],
    cli_name_contains: str | None,
    file_criteria: SelectionCriteria | None,
) -> SelectionCriteria:
    ids = set(cli_template_ids)
    name_contains = cli_name_contains
    if file_criteria:
        ids |= file_criteria.template_ids
        if name_contains is None:
            name_contains = file_criteria.name_contains
    return SelectionCriteria(template_ids=ids, name_contains=name_contains)


def select_templates(
    available: list[TemplateSummary],
    criteria: SelectionCriteria,
    *,
    strict_ids: bool = True,
) -> list[TemplateSummary]:
    selected = available

    if criteria.template_ids:
        selected = [template for template in selected if template.template_id in criteria.template_ids]
        if strict_ids:
            found_ids = {template.template_id for template in selected}
            missing_ids = sorted(criteria.template_ids - found_ids)
            if missing_ids:
                missing_text = ", ".join(missing_ids)
                raise ValueError(f"Template IDs not found in source platform: {missing_text}")

    if criteria.name_contains:
        term = criteria.name_contains.casefold()
        selected = [template for template in selected if term in template.name.casefold()]

    # stable ordering makes reports deterministic
    return sorted(selected, key=lambda template: template.name.casefold())

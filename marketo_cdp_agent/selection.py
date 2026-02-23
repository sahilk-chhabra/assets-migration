from __future__ import annotations

import json
from dataclasses import dataclass

from marketo_cdp_agent.models import LeadSummary


@dataclass(frozen=True)
class SelectionCriteria:
    lead_ids: set[str]
    email_contains: str | None = None


def parse_lead_ids(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {chunk.strip() for chunk in raw.split(",") if chunk.strip()}


def load_selection_file(path: str) -> SelectionCriteria:
    with open(path, "r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    if isinstance(payload, list):
        ids = {str(item).strip() for item in payload if str(item).strip()}
        return SelectionCriteria(lead_ids=ids, email_contains=None)

    if isinstance(payload, dict):
        ids_raw = payload.get("lead_ids") or payload.get("ids") or []
        ids = {str(item).strip() for item in ids_raw if str(item).strip()}
        email_contains = payload.get("email_contains")
        if email_contains is not None and not isinstance(email_contains, str):
            raise ValueError("selection file field 'email_contains' must be a string")
        return SelectionCriteria(lead_ids=ids, email_contains=email_contains)

    raise ValueError("selection file must be a JSON array or object")


def merge_criteria(
    cli_lead_ids: set[str],
    cli_email_contains: str | None,
    file_criteria: SelectionCriteria | None,
) -> SelectionCriteria:
    ids = set(cli_lead_ids)
    email_contains = cli_email_contains
    if file_criteria:
        ids |= file_criteria.lead_ids
        if email_contains is None:
            email_contains = file_criteria.email_contains
    return SelectionCriteria(lead_ids=ids, email_contains=email_contains)


def select_leads(
    available: list[LeadSummary],
    criteria: SelectionCriteria,
    *,
    strict_ids: bool = True,
) -> list[LeadSummary]:
    selected = available

    if criteria.lead_ids:
        selected = [lead for lead in selected if lead.lead_id in criteria.lead_ids]
        if strict_ids:
            found_ids = {lead.lead_id for lead in selected}
            missing_ids = sorted(criteria.lead_ids - found_ids)
            if missing_ids:
                missing_text = ", ".join(missing_ids)
                raise ValueError(f"Lead IDs not found in source platform: {missing_text}")

    if criteria.email_contains:
        term = criteria.email_contains.casefold()
        selected = [lead for lead in selected if term in (lead.email or "").casefold()]

    # Stable ordering keeps reports deterministic.
    return sorted(selected, key=lambda lead: (lead.email or "", lead.lead_id))

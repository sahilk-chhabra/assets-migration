from __future__ import annotations

import json
from datetime import datetime, timezone

from marketo_cdp_agent.models import MigrationResult


def build_report(
    results: list[MigrationResult],
    *,
    dry_run: bool,
    selected_count: int,
    source_count: int,
) -> dict[str, object]:
    status_counts = {"migrated": 0, "failed": 0, "dry_run": 0}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "source_count": source_count,
        "selected_count": selected_count,
        "result_count": len(results),
        "status_counts": status_counts,
        "results": [
            {
                "lead_id": row.lead_id,
                "lead_name": row.lead_name,
                "status": row.status,
                "destination_id": row.destination_id,
                "message": row.message,
            }
            for row in results
        ],
    }


def write_report(path: str, report: dict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(report, file_obj, indent=2)
        file_obj.write("\n")

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone

from email_migration_agent.models import MigrationResult


def write_report(
    path: str,
    *,
    direction: str,
    selected_count: int,
    results: list[MigrationResult],
) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "direction": direction,
        "selected_count": selected_count,
        "summary": _summarize(results),
        "results": [asdict(row) for row in results],
    }
    with open(path, "w", encoding="utf-8") as file_obj:
        json.dump(payload, file_obj, indent=2, ensure_ascii=True)
        file_obj.write("\n")


def _summarize(results: list[MigrationResult]) -> dict[str, int]:
    counts = {"migrated": 0, "failed": 0, "dry_run": 0}
    for row in results:
        counts[row.status] = counts.get(row.status, 0) + 1
    counts["total"] = len(results)
    return counts

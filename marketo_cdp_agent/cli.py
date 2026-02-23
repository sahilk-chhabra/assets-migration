from __future__ import annotations

import argparse
import sys

from marketo_cdp_agent.agent import MarketoCdpMigrationAgent
from marketo_cdp_agent.cdp import CdpClient
from marketo_cdp_agent.config import load_config
from marketo_cdp_agent.marketo import MarketoClient
from marketo_cdp_agent.reporting import build_report, write_report
from marketo_cdp_agent.selection import (
    SelectionCriteria,
    load_selection_file,
    merge_criteria,
    parse_lead_ids,
    select_leads,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate selected Marketo leads into CDP")
    parser.add_argument("--config", required=True, help="Path to config JSON file")
    parser.add_argument("--lead-ids", default=None, help="Comma-separated Marketo lead IDs")
    parser.add_argument("--selection-file", default=None, help="Optional JSON selection file")
    parser.add_argument("--email-contains", default=None, help="Optional email substring filter")
    parser.add_argument(
        "--allow-missing-ids",
        action="store_true",
        help="Do not fail if selected lead IDs are not found in Marketo",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not write data to CDP")
    parser.add_argument(
        "--report-file",
        default="migration-report.json",
        help="Path for JSON migration report",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config = load_config(args.config)
    marketo = MarketoClient(config.marketo)
    cdp = CdpClient(config.cdp)

    file_criteria = load_selection_file(args.selection_file) if args.selection_file else None
    criteria = merge_criteria(parse_lead_ids(args.lead_ids), args.email_contains, file_criteria)
    _validate_non_empty_selection(criteria, parser)

    leads = marketo.get_leads_by_ids(criteria.lead_ids)
    summaries = [lead.to_summary() for lead in leads]
    selected = select_leads(
        summaries,
        criteria,
        strict_ids=not args.allow_missing_ids,
    )

    selected_by_id = {row.lead_id for row in selected}
    selected_leads = [lead for lead in leads if lead.lead_id in selected_by_id]

    agent = MarketoCdpMigrationAgent(cdp, batch_size=config.cdp.batch_size)
    results = agent.migrate(selected_leads, dry_run=args.dry_run)

    report = build_report(
        results,
        dry_run=args.dry_run,
        selected_count=len(selected_leads),
        source_count=len(leads),
    )
    write_report(args.report_file, report)

    migrated = report["status_counts"].get("migrated", 0)
    failed = report["status_counts"].get("failed", 0)
    dry_run_count = report["status_counts"].get("dry_run", 0)
    print(
        f"Completed migration run: migrated={migrated} "
        f"dry_run={dry_run_count} failed={failed} report={args.report_file}"
    )

    return 1 if failed else 0


def _validate_non_empty_selection(
    criteria: SelectionCriteria,
    parser: argparse.ArgumentParser,
) -> None:
    if criteria.lead_ids:
        return
    parser.error("At least one lead ID must be provided via --lead-ids or --selection-file")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

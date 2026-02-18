from __future__ import annotations

import argparse
import sys

from email_migration_agent.agent import MigrationAgent
from email_migration_agent.config import AgentConfig, load_config
from email_migration_agent.platforms import HubSpotClient, MarketoClient
from email_migration_agent.platforms.base import PlatformClient
from email_migration_agent.reporting import write_report
from email_migration_agent.selection import (
    SelectionCriteria,
    load_selection_file,
    merge_criteria,
    parse_template_ids,
    select_templates,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Migrate selected email templates between Marketo and HubSpot."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to JSON config file (see config.example.json).",
    )
    parser.add_argument(
        "--direction",
        required=True,
        choices=("marketo_to_hubspot", "hubspot_to_marketo"),
        help="Migration direction.",
    )
    parser.add_argument(
        "--template-ids",
        default="",
        help="Comma-separated template IDs to migrate from source platform.",
    )
    parser.add_argument(
        "--selection-file",
        default=None,
        help=(
            "Optional JSON file containing template IDs and optional name_contains. "
            "Format: [\"id1\", \"id2\"] or {\"template_ids\":[...],\"name_contains\":\"...\"}"
        ),
    )
    parser.add_argument(
        "--name-contains",
        default=None,
        help="Optional case-insensitive name filter applied after template-id filtering.",
    )
    parser.add_argument(
        "--allow-missing-ids",
        action="store_true",
        help="Do not fail when a requested template ID is not found on source platform.",
    )
    parser.add_argument(
        "--target-name-prefix",
        default=None,
        help="Optional prefix to apply to destination template names.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and transform templates but do not write to destination.",
    )
    parser.add_argument(
        "--report-file",
        default="migration-report.json",
        help="Path to write JSON migration report.",
    )
    return parser.parse_args(argv)


def build_clients(config: AgentConfig, direction: str) -> tuple[PlatformClient, PlatformClient, str, str]:
    marketo = MarketoClient(config.marketo)
    hubspot = HubSpotClient(config.hubspot)
    if direction == "marketo_to_hubspot":
        return marketo, hubspot, "marketo", "hubspot"
    return hubspot, marketo, "hubspot", "marketo"


def _criteria_from_args(args: argparse.Namespace) -> SelectionCriteria:
    cli_ids = parse_template_ids(args.template_ids)
    file_criteria = load_selection_file(args.selection_file) if args.selection_file else None
    return merge_criteria(cli_ids, args.name_contains, file_criteria)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    source_client, destination_client, source_label, destination_label = build_clients(
        config, args.direction
    )

    print(f"Fetching source templates from {source_label}...")
    available = source_client.list_templates()
    print(f"Discovered {len(available)} templates in {source_label}.")

    criteria = _criteria_from_args(args)
    selected = select_templates(
        available,
        criteria,
        strict_ids=not args.allow_missing_ids,
    )
    if not selected:
        print("No templates selected. Nothing to migrate.")
        write_report(args.report_file, direction=args.direction, selected_count=0, results=[])
        print(f"Wrote report to {args.report_file}")
        return 0

    print(f"Selected {len(selected)} templates for migration.")
    agent = MigrationAgent(
        source_client,
        destination_client,
        source_label=source_label,
        destination_label=destination_label,
        target_name_prefix=args.target_name_prefix,
    )

    results = agent.migrate(selected, dry_run=args.dry_run)
    write_report(
        args.report_file,
        direction=args.direction,
        selected_count=len(selected),
        results=results,
    )
    _print_summary(results, report_path=args.report_file)

    has_failures = any(row.status == "failed" for row in results)
    return 2 if has_failures else 0


def _print_summary(results, *, report_path: str) -> None:
    migrated = sum(1 for row in results if row.status == "migrated")
    failed = sum(1 for row in results if row.status == "failed")
    dry_run = sum(1 for row in results if row.status == "dry_run")
    total = len(results)

    print("\nMigration summary")
    print("-----------------")
    print(f"Total:    {total}")
    print(f"Migrated: {migrated}")
    print(f"Dry-run:  {dry_run}")
    print(f"Failed:   {failed}")
    print(f"Report:   {report_path}")

    if failed:
        print("\nFailures")
        print("--------")
        for row in results:
            if row.status == "failed":
                print(f"- {row.source_name} (id={row.source_id}): {row.message}")


if __name__ == "__main__":
    sys.exit(main())

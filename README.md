# Marketo CDP Integration Agent

This project provides a CLI agent to move selected lead/profile data from **Marketo** into a generic **Customer Data Platform (CDP)** ingestion API.

## Features

- Marketo OAuth token flow with client credentials
- Lead selection by:
  - comma-separated IDs (`--lead-ids`)
  - JSON selection file (`--selection-file`)
  - optional email substring filter (`--email-contains`)
- Dry-run mode (`--dry-run`) to validate selection and mapping without writing to CDP
- Batched CDP ingestion
- JSON migration report with per-lead success/failure status

## Quick Start

### 1) Prepare config

```bash
cp config.example.json config.json
```

Set credentials in your shell:

```bash
export MARKETO_CLIENT_ID="..."
export MARKETO_CLIENT_SECRET="..."
export CDP_API_KEY="..."
```

### 2) Run a dry-run

```bash
python run_migration.py \
  --config config.json \
  --lead-ids 1001,1002,1003 \
  --dry-run \
  --report-file migration-report.json
```

### 3) Execute ingestion

```bash
python run_migration.py \
  --config config.json \
  --lead-ids 1001,1002,1003 \
  --report-file migration-report.json
```

## Selection File Format

Use either a JSON array:

```json
["1001", "1002", "1003"]
```

Or a JSON object:

```json
{
  "lead_ids": ["1001", "1002", "1003"],
  "email_contains": "@example.com"
}
```

## Command Reference

```text
--config <path>                 Required config file path
--lead-ids <csv>                Optional source Marketo lead IDs
--selection-file <path>         Optional JSON file for IDs/filter
--email-contains <text>         Optional case-insensitive email filter
--allow-missing-ids             Do not fail when requested IDs are missing
--dry-run                       No CDP writes
--report-file <path>            Report output path (default: migration-report.json)
```

## Notes

- This agent fetches Marketo leads by explicit IDs for predictable, auditable migrations.
- Endpoint paths are configurable in `config.json` for environments that expose different Marketo/CDP routes.

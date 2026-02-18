# Email Template Migration Agent (Marketo <> HubSpot)

This project provides a CLI agent that migrates **selected email templates** between:

- Marketo -> HubSpot
- HubSpot -> Marketo

It is designed to support selective migrations (specific IDs and/or name filters), dry-run validation, and migration reporting.

## Features

- Bi-directional migration (`marketo_to_hubspot` and `hubspot_to_marketo`)
- Select templates by:
  - comma-separated template IDs (`--template-ids`)
  - JSON selection file (`--selection-file`)
  - name contains filter (`--name-contains`)
- Dry-run mode (`--dry-run`) to verify selection and fetch behavior before writing
- Upsert behavior in destination platform (update if name exists, otherwise create)
- JSON report output with per-template success/failure details
- Endpoint overrides in config to adapt to account-specific API versions/routes

## Quick Start

### 1) Prepare config

Copy and edit the example config:

```bash
cp config.example.json config.json
```

Set credentials in your environment:

```bash
export MARKETO_CLIENT_ID="..."
export MARKETO_CLIENT_SECRET="..."
export HUBSPOT_ACCESS_TOKEN="..."
```

`config.json` supports `${ENV_VAR}` placeholders and resolves them at runtime.

### 2) Run a dry-run migration

Marketo -> HubSpot:

```bash
python run_migration.py \
  --config config.json \
  --direction marketo_to_hubspot \
  --template-ids 101,102,103 \
  --dry-run \
  --report-file migration-report.json
```

HubSpot -> Marketo with name filter:

```bash
python run_migration.py \
  --config config.json \
  --direction hubspot_to_marketo \
  --name-contains "welcome" \
  --dry-run
```

### 3) Execute migration

Remove `--dry-run` after validation:

```bash
python run_migration.py \
  --config config.json \
  --direction marketo_to_hubspot \
  --template-ids 101,102,103 \
  --report-file migration-report.json
```

## Selection File Format

Use either JSON array:

```json
["101", "102", "103"]
```

Or JSON object:

```json
{
  "template_ids": ["101", "102", "103"],
  "name_contains": "newsletter"
}
```

Then run:

```bash
python run_migration.py \
  --config config.json \
  --direction marketo_to_hubspot \
  --selection-file selection.json
```

## Command Reference

```text
--config <path>                 Required config file path
--direction <value>             marketo_to_hubspot | hubspot_to_marketo
--template-ids <csv>            Optional source template IDs
--selection-file <path>         Optional JSON file for IDs/filter
--name-contains <text>          Optional case-insensitive name filter
--allow-missing-ids             Do not fail when requested IDs are missing
--target-name-prefix <text>     Prefix destination template names
--dry-run                       No destination writes
--report-file <path>            Report output path (default: migration-report.json)
```

## Notes on API Differences

Marketo and HubSpot email/template APIs differ by account version and scope.  
If an endpoint is different in your environment, override it under `marketo.endpoints` or `hubspot.endpoints` in `config.json`.

The agent preserves the template name/subject/html/text where available, and records migration outcomes in the report file.

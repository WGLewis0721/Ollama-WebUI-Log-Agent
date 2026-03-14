# misc/

This folder preserves files from the active development and build phases of the
Log Analyst Agent v3. Nothing here is required to deploy or run the project.

## Contents

| Folder | What's inside |
|---|---|
| `agent-bak/` | Timestamped .bak snapshots and superseded agent modules (main.py, main_opensearch.py, rag_indexer.py, s3_document_fetcher.py) |
| `compose-backups/` | Backup and variant docker-compose files from the build phase |
| `scripts/` | One-time deployment, patching, and fix scripts used during initial setup |
| `docs/` | Working notes, option analysis docs, and integration guides from the build phase |
| `secrets/` | Environment file examples with placeholder values — do not commit real credentials |
| `output/` | Captured terminal output from deployment validation runs |
| `root-duplicates/` | Stale root-level copies of Python modules that live in agent/ |

#!/bin/bash
set -euo pipefail

ENV_FILE=".env.rag"
COMPOSE_FILE="docker-compose-rag.yml"

echo "==> 1. Updating lookback window to 48 hours (2880 minutes)..."
sed -i 's/TIME_RANGE_MINUTES=.*/TIME_RANGE_MINUTES=2880/' "$ENV_FILE"

echo "==> 2. Restarting Agent..."
docker compose -f "$COMPOSE_FILE" up -d log-analyst-rag

echo "==> 3. Monitoring logs (Ctrl+C to exit tailing)..."
sleep 2
docker compose -f "$COMPOSE_FILE" logs -f log-analyst-rag

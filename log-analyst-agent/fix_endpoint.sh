#!/bin/bash
set -euo pipefail

ENV_FILE=".env.rag"
COMPOSE_FILE="docker-compose-rag.yml"

echo "==> 1. Cleaning OPENSEARCH_ENDPOINT in $ENV_FILE..."
# Removes https:// or http:// if present
sed -i 's|OPENSEARCH_ENDPOINT=https://|OPENSEARCH_ENDPOINT=|g' "$ENV_FILE"
sed -i 's|OPENSEARCH_ENDPOINT=http://|OPENSEARCH_ENDPOINT=|g' "$ENV_FILE"

echo "==> 2. Verifying the change..."
grep "OPENSEARCH_ENDPOINT" "$ENV_FILE"

echo "==> 3. Restarting Stack..."
docker compose -f "$COMPOSE_FILE" up -d

echo "==> 4. Tailining logs (Ctrl+C to stop)..."
sleep 2
docker compose -f "$COMPOSE_FILE" logs -f log-analyst-rag

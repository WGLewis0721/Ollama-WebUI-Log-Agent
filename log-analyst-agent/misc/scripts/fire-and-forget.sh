#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="docker-compose-opensearch.yml"

echo "=== 0) Preconditions ==="
[[ -f "$COMPOSE_FILE" ]] || { echo "❌ Missing $COMPOSE_FILE in $(pwd)"; exit 1; }
[[ -f "agent/dashboard.py" ]] || { echo "❌ Missing agent/dashboard.py"; exit 1; }
[[ -f "agent/templates/dashboard.html" ]] || { echo "❌ Missing agent/templates/dashboard.html"; exit 1; }

echo "=== 1) Stop any existing stack and remove orphans ==="
docker compose down --remove-orphans || true
docker compose -f "$COMPOSE_FILE" down --remove-orphans || true

echo "=== 2) Start original opensearch stack (agent loop + dashboard) ==="
docker compose -f "$COMPOSE_FILE" up -d --build

echo "=== 3) Detect containers ==="
# We try common names used by the repo. If your compose uses different names, this auto-detects.
DASH_CANDIDATES=(
  "log-analyst-dashboard"
  "dashboard"
  "log-analyst-agent-dashboard"
)

AGENT_CANDIDATES=(
  "log-analyst"
  "agent"
  "log-analyst-agent"
)

find_running() {
  local name
  for name in "$@"; do
    if docker ps --format '{{.Names}}' | grep -qx "$name"; then
      echo "$name"
      return 0
    fi
  done
  return 1
}

DASH_CONTAINER="$(find_running "${DASH_CANDIDATES[@]}" || true)"
AGENT_CONTAINER="$(find_running "${AGENT_CANDIDATES[@]}" || true)"

echo "Dashboard container: ${DASH_CONTAINER:-<not found>}"
echo "Agent container:      ${AGENT_CONTAINER:-<not found>}"

if [[ -z "${DASH_CONTAINER:-}" ]]; then
  echo "❌ Could not find dashboard container. Run: docker ps"
  exit 1
fi

echo "=== 4) Patch dashboard container with your updated UI + API ==="
docker cp agent/dashboard.py "$DASH_CONTAINER":/app/dashboard.py
docker cp agent/templates/dashboard.html "$DASH_CONTAINER":/app/templates/dashboard.html

echo "=== 5) Restart services cleanly ==="
docker compose -f "$COMPOSE_FILE" restart

echo "=== 6) Quick checks ==="
echo "--- Containers ---"
docker ps --format '{{.Names}}\t{{.Status}}\t{{.Ports}}' | egrep 'log-analyst|dashboard|ollama' || true

echo "--- Dashboard API (should show JSON, ideally with log_source) ---"
curl -s http://localhost:5000/api/reports | head -c 600 && echo

echo "--- Output directory (should keep growing every 5 min if agent is looping) ---"
ls -lt output 2>/dev/null | head || true

echo
echo "✅ Done."
echo "Next: watch the agent logs to confirm the 5-min loop:"
echo "  docker logs -f --tail 200 ${AGENT_CONTAINER:-log-analyst}"

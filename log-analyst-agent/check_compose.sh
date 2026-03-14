#!/bin/bash
set -euo pipefail

# Navigate to the directory
cd ~/log-analyst-agent

echo "== Compose: log-analyst-rag service block (raw) =="
# This awk script captures the block starting with log-analyst-rag
# and stops when it hits another top-level key.
awk '
  $0 ~ /^[[:space:]]*log-analyst-rag:[[:space:]]*$/ {found=1}
  found {print}
  found && $0 ~ /^[[:alnum:]_.-]+:[[:space:]]*$/ && $0 !~ /^[[:space:]]/ {found=0}
' docker-compose-rag.yml | sed -n "1,200p"

echo
echo "== Any hardcoded env hints in compose =="
grep -nE "MODEL_NAME|TIME_RANGE_MINUTES|RAG_K|MAX_LOGS|env_file:" docker-compose-rag.yml || true

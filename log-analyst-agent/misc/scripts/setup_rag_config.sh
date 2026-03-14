#!/bin/bash
set -euo pipefail

DIRECTORY="$HOME/log-analyst-agent"
COMPOSE_FILE="docker-compose-rag.yml"
ENV_FILE=".env.rag"

cd "$DIRECTORY"

echo "Step 1: Backing up $COMPOSE_FILE..."
cp -a "$COMPOSE_FILE" "$COMPOSE_FILE.bak.$(date +%Y%m%d_%H%M%S)"

echo "Step 2: Patching $COMPOSE_FILE (Injecting env_file, cleaning environment)..."
python3 - <<PY
import re, pathlib

p = pathlib.Path("$COMPOSE_FILE")
lines = p.read_text().splitlines(True)

def get_indent(s): return len(s) - len(s.lstrip(" "))

out = []
in_svc = False
svc_indent = 0
seen_env_file = False

# Variables we want to move from YAML to the .env file
managed_vars = ["MODEL_NAME", "TIME_RANGE_MINUTES", "RAG_K", "MAX_LOGS"]

for line in lines:
    # Match the service block start
    if re.match(r"^[ ]*log-analyst-rag:[ ]*$", line):
        in_svc = True
        svc_indent = get_indent(line)
        seen_env_file = False
        out.append(line)
        continue

    # Detect if we are leaving the service block (lower or same indent as service name)
    if in_svc and line.strip() and get_indent(line) <= svc_indent and not line.startswith(" "):
        if not seen_env_file:
            out.append(" " * (svc_indent + 4) + "env_file:\n")
            out.append(" " * (svc_indent + 6) + "- $ENV_FILE\n")
        in_svc = False

    if in_svc:
        # Check if env_file already exists
        if "env_file:" in line:
            seen_env_file = True
        
        # Remove specific hardcoded variables from the environment list
        if any(f"- {v}=" in line or f"{v}:" in line for v in managed_vars):
            continue
            
    out.append(line)

p.write_text("".join(out))
PY

echo "Step 3: Creating $ENV_FILE with default values..."
# We use '|| true' on grep so the script doesn't crash if a variable is missing
cat << ENV > "$ENV_FILE"
# --- Managed by Setup Script ---
MODEL_NAME=llama3
RAG_K=3
TIME_RANGE_MINUTES=5
MAX_LOGS=100

# --- Inherited from Compose ---
ANALYSIS_TYPE=general
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5
OPENSEARCH_ENDPOINT=
AWS_REGION=us-east-1
OPENSEARCH_INDEX=logs-*
APPLICATION_NAME=
ERRORS_ONLY=false
LOG_LEVEL=INFO
ENV

echo "Step 4: Final Verification..."
echo "--- New env_file block in YAML ---"
grep -A 2 "env_file:" "$COMPOSE_FILE"
echo "----------------------------------"
echo "SUCCESS: $COMPOSE_FILE patched and $ENV_FILE created."
echo "ACTION REQUIRED: Edit $ENV_FILE to add your OPENSEARCH_ENDPOINT."

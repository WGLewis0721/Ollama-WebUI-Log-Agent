#!/bin/bash
set -euo pipefail

DIRECTORY="$HOME/log-analyst-agent"
COMPOSE_FILE="docker-compose-rag.yml"
ENV_FILE=".env.rag"
ENDPOINT="https://vpc-dev-c-dev-cnap-il6-opensear-gsubaunjbfw3i6w2gnjfv4g6w4.us-gov-west-1.es.amazonaws.com"

cd "$DIRECTORY"

echo "==> 1. Backing up configuration..."
cp -a "$COMPOSE_FILE" "$COMPOSE_FILE.bak.$(date +%Y%m%d_%H%M%S)"

echo "==> 2. Patching YAML (env_file injection & cleanup)..."
python3 - <<PY
import re, pathlib
p = pathlib.Path("$COMPOSE_FILE")
content = p.read_text()

# Inject env_file block under log-analyst-rag
if "env_file:" not in content:
    content = re.sub(
        r"(log-analyst-rag:.*?)(environment:)",
        r"\1env_file:\n      - $ENV_FILE\n    \2", 
        content, 
        flags=re.DOTALL
    )

# Scrub hardcoded overrides
for key in ["MODEL_NAME", "RAG_K", "TIME_RANGE_MINUTES", "MAX_LOGS", "OPENSEARCH_ENDPOINT", "AWS_REGION"]:
    content = re.sub(rf"^[ ]*-[ ]*{key}=.*?\n", "", content, flags=re.MULTILINE)
    content = re.sub(rf"^[ ]*{key}:.*?\n", "", content, flags=re.MULTILINE)

p.write_text(content)
PY

echo "==> 3. Generating $ENV_FILE with GovCloud settings..."
cat << ENV > "$ENV_FILE"
# --- LLM & RAG ---
MODEL_NAME=llama3
RAG_K=3
TIME_RANGE_MINUTES=5
MAX_LOGS=100

# --- GovCloud Infrastructure ---
OPENSEARCH_ENDPOINT=$ENDPOINT
AWS_REGION=us-gov-west-1
OPENSEARCH_INDEX=logs-*
APPLICATION_NAME=
ERRORS_ONLY=false
LOG_LEVEL=INFO

# --- Connection ---
OLLAMA_BASE_URL=http://ollama:11434
ENV

echo "==> 4. Testing Network Connectivity to OpenSearch..."
# We check if the VPC endpoint is reachable on port 443
if curl -s -k --connect-timeout 5 "$ENDPOINT" > /dev/null; then
    echo "SUCCESS: Endpoint is reachable."
else
    echo "WARNING: Could not reach OpenSearch endpoint. Check your Security Groups/VPC Routing."
fi

echo "==> 5. Finalizing..."
echo "Opening $ENV_FILE in vim for review. Type :q to exit."
sleep 2
vim "$ENV_FILE"

echo "==> 6. Starting Docker Stack..."
docker compose -f "$COMPOSE_FILE" up -d

echo "------------------------------------------------"
echo "DEPLOYMENT COMPLETE"
echo "Use 'docker compose -f $COMPOSE_FILE logs -f' to watch the agent."
echo "------------------------------------------------"

#!/bin/bash
# =============================================================================
# phase4_openwebui_fix.sh — CNAP Log Analyst Agent
# Phase 4: Route OpenWebUI through the agent API instead of raw Ollama
# Run from: /home/ubuntu/log-analyst-agent
# Usage:    bash phase4_openwebui_fix.sh | tee phase4_output.txt
# =============================================================================

set -e

PROJECT="/home/ubuntu/log-analyst-agent"
COMPOSE_FILE="$PROJECT/docker-compose-rag.yml"

DIVIDER="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HDR() { echo ""; echo "$DIVIDER"; echo "  $1"; echo "$DIVIDER"; }

HDR "PHASE 4 — OpenWebUI Fix + Validation"
echo "  Goal: Route OpenWebUI through agent API (port 7000) not raw Ollama (11434)"

# ── 4.1 Backup compose file ───────────────────────────────────────────────────
HDR "4.1 · Backing up docker-compose-rag.yml"
cp "$COMPOSE_FILE" "$COMPOSE_FILE.bak.$(date +%s)"
echo "  ✓ Backup saved"

# ── 4.2 Rewrite the full compose file with OpenWebUI fix ─────────────────────
HDR "4.2 · Writing updated docker-compose-rag.yml"
cat > "$COMPOSE_FILE" << 'EOF'
networks:
  log-analyst-network:
    driver: bridge

services:

  ollama:
    container_name: ollama
    deploy:
      resources:
        reservations:
          devices:
            - capabilities: [gpu]
              count: all
              driver: nvidia
    environment:
      - OLLAMA_HOST=0.0.0.0
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    healthcheck:
      interval: 30s
      retries: 3
      test: ["CMD", "ollama", "list"]
      timeout: 10s
    image: ollama/ollama:0.15.5
    networks:
      - log-analyst-network
    ports:
      - "11434:11434"
    restart: unless-stopped
    volumes:
      - ollama_data:/root/.ollama

  log-analyst-rag:
    build:
      context: ./agent
      dockerfile: Dockerfile
    command: python -u api_server.py
    container_name: log-analyst-rag
    depends_on:
      ollama:
        condition: service_healthy
    env_file:
      - .env.rag
    networks:
      - log-analyst-network
    ports:
      - "7000:7000"
    restart: unless-stopped
    volumes:
      - ./output:/app/output
      - ./config:/app/config
      - ~/.aws:/root/.aws:ro

  dashboard:
    build:
      context: ./agent
      dockerfile: Dockerfile
    command: python dashboard.py
    container_name: log-analyst-dashboard
    depends_on:
      - log-analyst-rag
    environment:
      - OUTPUT_DIR=/app/output
      - DASHBOARD_PORT=5000
    networks:
      - log-analyst-network
    ports:
      - "5000:5000"
    restart: unless-stopped
    volumes:
      - ./output:/app/output:ro

  open-webui:
    build:
      context: .
      dockerfile: Dockerfile.open-webui
    container_name: open-webui
    depends_on:
      - log-analyst-rag
    environment:
      # ── Route all chat through the agent API, not raw Ollama ──
      - OPENAI_API_BASE_URL=http://log-analyst-rag:7000/v1
      - OPENAI_API_KEY=cnap-il6-key  # Any non-empty string; required by OpenWebUI
      # ── Disable direct Ollama connection ──
      - OLLAMA_BASE_URL=
      - ENABLE_OLLAMA_API=false
      # ── UI settings ──
      - WEBUI_AUTH=true
      - WEBUI_NAME=CNAP AI Assistant
      - DEFAULT_MODELS=log-analyst-rag
      - AWS_REGION=us-gov-west-1
    networks:
      - log-analyst-network
    ports:
      - "8080:8080"
    restart: unless-stopped
    volumes:
      - open-webui-data:/app/backend/data

volumes:
  ollama_data:
  open-webui-data:
EOF

echo "  ✓ docker-compose-rag.yml updated"

# ── 4.3 Restart only open-webui (agent stays running) ────────────────────────
HDR "4.3 · Restarting open-webui with new config"
sudo docker compose -f "$COMPOSE_FILE" up -d open-webui

echo "  ⏳ Waiting 15s for OpenWebUI to reinitialize..."
sleep 15

# ── 4.4 Verify env was applied ────────────────────────────────────────────────
HDR "4.4 · Verifying OpenWebUI environment"
echo "  Checking OPENAI_API_BASE_URL inside container:"
OAIURL=$(sudo docker exec open-webui env | grep OPENAI_API_BASE_URL || echo "NOT SET")
echo "  $OAIURL"

OLLAMAURL=$(sudo docker exec open-webui env | grep "OLLAMA_BASE_URL" || echo "NOT SET")
echo "  $OLLAMAURL"

if echo "$OAIURL" | grep -q "7000"; then
  echo "  ✅ PASS: OpenWebUI is pointed at agent port 7000"
else
  echo "  ❌ FAIL: OPENAI_API_BASE_URL not set correctly"
fi

# ── 4.5 Verify agent /v1/models is reachable from inside open-webui ──────────
HDR "4.5 · Connectivity — can open-webui reach the agent API?"
sudo docker exec open-webui curl -s --max-time 5 \
  http://log-analyst-rag:7000/v1/models \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
models = [m['id'] for m in d.get('data', [])]
print(f'  ✅ PASS: Agent reachable from open-webui. Models: {models}')
" 2>/dev/null || echo "  ❌ FAIL: open-webui cannot reach log-analyst-rag:7000"

# ── 4.6 Simulate what OpenWebUI sends — prove agent logic fires ───────────────
HDR "4.6 · End-to-end — simulate OpenWebUI chat request through agent"
echo "  Sending OpenAI-format request to agent (same format OpenWebUI uses)..."
echo "  Expect: 30-60 second response with RAG used = True"
echo ""

curl -s -X POST http://localhost:7000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer cnap-il6-key" \
  -d '{
    "model": "log-analyst-rag",
    "messages": [
      {"role": "system", "content": "You are the CNAP AI Assistant."},
      {"role": "user",   "content": "What security threats are visible in the current logs? Reference the runbook for recommended actions."}
    ]
  }' \
  --max-time 300 > /tmp/phase4_test.json

python3 -c "
import json
d    = json.load(open('/tmp/phase4_test.json'))
meta = d.get('metadata', {})
content = d['choices'][0]['message']['content']

print(f'  Log count : {meta.get(\"log_count\", \"?\")}')
print(f'  RAG used  : {meta.get(\"rag_used\", \"?\")}')
print(f'  Model     : {meta.get(\"model\", \"?\")}')
print(f'  Length    : {len(content)} chars')
print()

if meta.get('rag_used'):
    print('  ✅ PASS: RAG context injected — OpenWebUI gets full agent analysis')
else:
    print('  ⚠️  WARN: RAG not used — knowledge-base may need more docs')

print()
print('  Response preview (first 800 chars):')
print('  ' + content[:800].replace(chr(10), chr(10) + '  '))
"

# ── 4.7 Container status summary ─────────────────────────────────────────────
HDR "4.7 · All containers status"
sudo docker compose -f "$COMPOSE_FILE" ps

# ── Summary ───────────────────────────────────────────────────────────────────
HDR "PHASE 4 SUMMARY"
cat << 'SUMMARY'
  Request flow after this fix:
  
  User types in OpenWebUI (8080)
       ↓
  OpenWebUI sends POST /v1/chat/completions
       ↓
  log-analyst-rag API server (7000)
       ↓  ↓  ↓
  OpenSearch   RAG chunks   Ollama llama3.1:8b
       ↓
  Structured security analysis returned to OpenWebUI
  
  To access OpenWebUI:
    SSM port forward:  --parameters '{"portNumber":["8080"],"localPortNumber":["8080"]}'
    Then open:         http://localhost:8080
  
  Post-Fix Steps in UI:
    - Go to Settings → Models/Connections
    - Ensure 'log-analyst-rag' appears (from agent /v1/models)
    - Select it as default
    - Test query: "Analyze the last 30 minutes of security logs."
      (Expect: Logs referenced, RAG used: True in response/agent logs)

  If all checks passed → Proceed to Phase 5 (deployment guide + GitLab)
SUMMARY

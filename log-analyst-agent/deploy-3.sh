#!/bin/bash
# =============================================================================
# deploy_v3.sh — CNAP Log Analyst Agent v3
# Deploys text-to-query architecture:
#   - query_generator.py  (new)
#   - opensearch_executor.py (new)
#   - api_server.py v3    (updated — dual-mode routing)
# Dashboard :5000 route update is manual — see step 4 below
# Run from: /home/ubuntu/log-analyst-agent
# Usage:    bash deploy_v3.sh | tee deploy_v3_output.txt
# =============================================================================

set -e
PROJECT="/home/ubuntu/log-analyst-agent"
AGENT="$PROJECT/agent"
COMPOSE="$PROJECT/docker-compose-rag.yml"

DIVIDER="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HDR() { echo ""; echo "$DIVIDER"; echo "  $1"; echo "$DIVIDER"; }

HDR "DEPLOY v3 — Text-to-Query Architecture"

# ── Step 1 — Backup existing agent files ─────────────────────────────────────
HDR "Step 1 · Backup"
TS=$(date +%s)
cp "$AGENT/api_server.py" "$AGENT/api_server.py.bak.$TS"
echo "  ✓ api_server.py backed up"

# ── Step 2 — Copy new files into agent/ ──────────────────────────────────────
HDR "Step 2 · Copy new files"

# These files must be in the same directory as this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for f in query_generator.py opensearch_executor.py api_server.py; do
    if [ -f "$SCRIPT_DIR/$f" ]; then
        cp "$SCRIPT_DIR/$f" "$AGENT/$f"
        echo "  ✓ $f → agent/$f"
    else
        echo "  ❌ MISSING: $f not found in $SCRIPT_DIR"
        echo "     Upload it first: scp $f ubuntu@<EC2>:~/log-analyst-agent/"
        exit 1
    fi
done

# ── Step 3 — Add QUERY_MODEL to .env.rag if not present ──────────────────────
HDR "Step 3 · Environment"
if grep -q "QUERY_MODEL" "$PROJECT/.env.rag"; then
    echo "  ✓ QUERY_MODEL already in .env.rag"
else
    echo "QUERY_MODEL=llama3.2:3b" >> "$PROJECT/.env.rag"
    echo "  ✓ Added QUERY_MODEL=llama3.2:3b to .env.rag"
fi

# ── Step 4 — Add /latest_query route to dashboard.py ─────────────────────────
HDR "Step 4 · Dashboard route patch"
if grep -q "latest_query" "$AGENT/dashboard.py"; then
    echo "  ✓ /latest_query route already in dashboard.py"
else
    python3 << 'PYEOF'
path = '/home/ubuntu/log-analyst-agent/agent/dashboard.py'
content = open(path).read()

new_route = '''

@app.route('/latest_query')
def latest_query():
    """Show the most recent query-mode result with raw OpenSearch query."""
    import json
    from pathlib import Path
    output_dir = os.getenv('OUTPUT_DIR', '/app/output')
    fpath = Path(output_dir) / 'latest_query.json'
    if not fpath.exists():
        return render_template_string("""
        <h2>No query results yet</h2>
        <p>Send a specific question to the agent via OpenWebUI first.</p>
        <p><a href="/">← Back to dashboard</a></p>
        """)
    data = json.loads(fpath.read_text())
    return render_template_string("""
<!DOCTYPE html>
<html>
<head>
<title>Latest Query Result</title>
<style>
body { font-family: monospace; margin: 40px; background: #0d1117; color: #c9d1d9; }
h1 { color: #58a6ff; }
h2 { color: #79c0ff; border-bottom: 1px solid #30363d; padding-bottom: 8px; }
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin: 16px 0; }
pre { background: #0d1117; border: 1px solid #30363d; padding: 16px; border-radius: 6px;
      overflow-x: auto; color: #a5d6ff; font-size: 13px; white-space: pre-wrap; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
         background: #1f6feb; color: white; font-size: 12px; margin: 2px; }
a { color: #58a6ff; }
.copy-btn { background: #238636; color: white; border: none; padding: 6px 12px;
            border-radius: 6px; cursor: pointer; float: right; font-size: 12px; }
</style>
</head>
<body>
<h1>🔍 Latest Query Result</h1>
<p><a href="/">← Dashboard</a></p>

<div class="card">
  <h2>Question</h2>
  <p>{{ data.user_question }}</p>
  <span class="badge">{{ data.total_hits }} hits</span>
  <span class="badge">{{ data.indices_searched }}</span>
</div>

<div class="card">
  <h2>AI Explanation</h2>
  <p style="white-space: pre-wrap; line-height: 1.6;">{{ data.explanation }}</p>
</div>

<div class="card">
  <h2>Generated OpenSearch Query
    <button class="copy-btn" onclick="copyQuery()">Copy</button>
  </h2>
  <p style="color:#8b949e; font-size:13px;">
    Verify in OpenSearch Dev Tools:<br>
    <code>POST /{{ data.indices_searched }}/_search</code>
  </p>
  <pre id="query-json">{{ query_json }}</pre>
</div>

{% if data.aggregations %}
<div class="card">
  <h2>Aggregation Results</h2>
  <pre>{{ aggs_json }}</pre>
</div>
{% endif %}

{% if data.sample_hits %}
<div class="card">
  <h2>Sample Log Entries ({{ data.sample_hits|length }})</h2>
  <pre>{{ hits_json }}</pre>
</div>
{% endif %}

<script>
function copyQuery() {
  navigator.clipboard.writeText(document.getElementById('query-json').textContent);
  document.querySelector('.copy-btn').textContent = 'Copied!';
  setTimeout(() => document.querySelector('.copy-btn').textContent = 'Copy', 2000);
}
</script>
</body>
</html>
""",
        data=data,
        query_json=json.dumps(data.get('generated_query', {}), indent=2),
        aggs_json=json.dumps(data.get('aggregations', {}), indent=2),
        hits_json=json.dumps(data.get('sample_hits', [])[:10], indent=2, default=str)
    )
'''

# Find a good insertion point — before the last route or at end of routes
import_line = "from flask import"
if import_line not in content:
    print("WARNING: Could not find Flask import in dashboard.py — skipping route patch")
else:
    # Insert before if __name__ block
    if "if __name__" in content:
        content = content.replace("if __name__", new_route + "\n\nif __name__")
    else:
        content += new_route
    open(path, 'w').write(content)
    print("  ✓ /latest_query route added to dashboard.py")
PYEOF
fi

# ── Step 5 — Rebuild and restart ─────────────────────────────────────────────
HDR "Step 5 · Rebuild"
cd "$PROJECT"
sudo docker compose -f "$COMPOSE" build --no-cache log-analyst-rag
sudo docker compose -f "$COMPOSE" up -d log-analyst-rag

echo "  ⏳ Waiting 10s for container to start..."
sleep 10

# ── Step 6 — Smoke test: health check ────────────────────────────────────────
HDR "Step 6 · Health check"
curl -s http://localhost:7000/health | python3 -m json.tool || echo "  ❌ Health check failed"

# ── Step 7 — Smoke test: query mode ──────────────────────────────────────────
HDR "Step 7 · Query mode smoke test"
echo "  Asking: 'What are the top 5 source IPs by frequency?'"
echo "  (This should use query mode, not report mode)"
echo ""

curl -s -X POST http://localhost:7000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"What are the top 5 source IPs by frequency in the logs?"}]}' \
  --max-time 120 > /tmp/v3_query_test.json

python3 -c "
import json
d = json.load(open('/tmp/v3_query_test.json'))
m = d.get('metadata', {})
print(f'  Mode     : {m.get(\"mode\", \"?\")}')
print(f'  Hits     : {m.get(\"hit_count\", \"?\")}')
print(f'  RAG used : {m.get(\"rag_used\", \"?\")}')
print()
content = d['choices'][0]['message']['content']
print(content[:800])
"

# ── Step 8 — Smoke test: report mode ─────────────────────────────────────────
HDR "Step 8 · Report mode smoke test"
echo "  Asking: 'Analyze recent security logs'"
echo "  (This should use report mode)"
echo ""

curl -s -X POST http://localhost:7000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Analyze recent security logs"}]}' \
  --max-time 300 > /tmp/v3_report_test.json

python3 -c "
import json
d = json.load(open('/tmp/v3_report_test.json'))
m = d.get('metadata', {})
print(f'  Mode     : {m.get(\"mode\", \"?\")}')
print(f'  Logs     : {m.get(\"log_count\", \"?\")}')
print(f'  RAG used : {m.get(\"rag_used\", \"?\")}')
print()
print(d['choices'][0]['message']['content'][:600])
"

# ── Step 9 — Check dashboard payload ─────────────────────────────────────────
HDR "Step 9 · Dashboard payload"
curl -s http://localhost:7000/v1/latest_query | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'  Question : {d.get(\"user_question\", \"\")[:80]}')
print(f'  Total hits: {d.get(\"total_hits\")}')
print(f'  Query    : {json.dumps(d.get(\"generated_query\",{}))[:150]}')
" 2>/dev/null || echo "  No query result yet — run step 7 first"

HDR "DEPLOY v3 COMPLETE"
cat << 'DONE'
  Architecture now active:

  Specific question  →  llama3.2:3b generates DSL  →  OpenSearch executes
                     →  llama3.1:8b explains results
                     →  Query visible in OpenWebUI + dashboard

  Generic request    →  Fetch 315 logs  →  RAG  →  Full SOC report

  Dashboard:
    http://localhost:5000              ← existing reports
    http://localhost:5000/latest_query ← new: query result + raw DSL + copy button

  Test queries to try in OpenWebUI (select log-analyst-rag model):
    "What are the top 5 source IPs by frequency?"
    "Show me the most recent 10 log entries"
    "Which firewall rule was hit most often?"
    "List all unique destination IPs"
    "How many logs came from appgate vs palo alto?"
DONE


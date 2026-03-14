#!/bin/bash
# =============================================================================
# deploy_main_rag.sh
# Writes the real main_rag.py, rebuilds the agent container, and tails logs
# Run from: /home/ubuntu/log-analyst-agent
# Usage:    bash deploy_main_rag.sh
# =============================================================================

set -e

AGENT_DIR="/home/ubuntu/log-analyst-agent/agent"
COMPOSE_FILE="/home/ubuntu/log-analyst-agent/docker-compose-rag.yml"
TARGET="$AGENT_DIR/main_rag.py"

# ── 1. Backup existing file ────────────────────────────────────────────────────
echo "📦 Backing up existing main_rag.py..."
cp "$TARGET" "$TARGET.bak.$(date +%s)" && echo "   ✓ Backup saved"

# ── 2. Write the real main_rag.py ─────────────────────────────────────────────
echo "✍️  Writing new main_rag.py..."
cat > "$TARGET" << 'PYEOF'
#!/usr/bin/env python3
"""
main_rag.py - Real bridge module imported by api_server.py
Wires opensearch_integration.py + rag_module.py into callable functions.
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
from typing import List, Dict
from pathlib import Path

# ── Environment ────────────────────────────────────────────────────────────────
OPENSEARCH_ENDPOINT = os.environ.get('OPENSEARCH_ENDPOINT', '')
AWS_REGION          = os.getenv('AWS_REGION', 'us-gov-west-1')
OPENSEARCH_INDEX    = os.getenv('OPENSEARCH_INDEX', 'cwl-*,appgate-logs-*,security-logs-*')
OLLAMA_BASE_URL     = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434')
MODEL_NAME          = os.getenv('MODEL_NAME', 'llama3.1:8b')
EMBED_MODEL         = 'nomic-embed-text'
ENABLE_RAG          = os.getenv('ENABLE_RAG', 'true').lower() == 'true'
RAG_K               = int(os.getenv('RAG_K', '3'))
RAG_INDEX           = os.getenv('RAG_INDEX', 'knowledge-base')
TIME_RANGE_MINUTES  = int(os.getenv('TIME_RANGE_MINUTES', '64800'))
WATCH_MODE          = os.getenv('WATCH_MODE', 'true').lower() == 'true'
WATCH_INTERVAL      = int(os.getenv('WATCH_INTERVAL_MINUTES', '30'))
OUTPUT_DIR          = Path(os.getenv('OUTPUT_DIR', '/app/output'))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Cached OpenSearch client ───────────────────────────────────────────────────
_os_client = None

def get_opensearch_client():
    """Return a cached OpenSearch client using container IAM credentials."""
    global _os_client
    if _os_client is not None:
        return _os_client
    from opensearch_integration import OpenSearchLogFetcher
    _os_client = OpenSearchLogFetcher(OPENSEARCH_ENDPOINT, AWS_REGION)
    return _os_client


# ── Log fetching ───────────────────────────────────────────────────────────────
def fetch_logs(client, index_pattern: str = None, time_range_minutes: int = None) -> List[Dict]:
    """Fetch and normalize logs from all configured index patterns."""
    index_pattern      = index_pattern or OPENSEARCH_INDEX
    time_range_minutes = time_range_minutes or TIME_RANGE_MINUTES
    all_logs = []

    for idx in index_pattern.split(','):
        idx = idx.strip()
        try:
            raw = client.fetch_logs(
                index_pattern=idx,
                time_range_minutes=time_range_minutes,
                max_logs=300
            )
            normalized = [_normalize(log, idx) for log in raw]
            all_logs.extend(normalized)
            print(f"  ✓ {idx}: {len(normalized)} logs")
        except Exception as e:
            print(f"  ✗ {idx}: {e}")

    return all_logs


def _normalize(src: Dict, index: str) -> Dict:
    """Normalize a raw OpenSearch document into a consistent structure."""
    ts = src.get('@timestamp', src.get('timestamp', ''))

    if 'cwl-' in index:
        msg   = src.get('@message', src.get('message', ''))
        parts = msg.split(',') if msg else []
        return {
            'timestamp': ts, 'index': index, 'type': 'palo_alto',
            'src_ip':  parts[7]  if len(parts) > 7  else '',
            'dst_ip':  parts[8]  if len(parts) > 8  else '',
            'rule':    parts[11] if len(parts) > 11 else '',
            'action':  parts[14] if len(parts) > 14 else '',
            'raw':     msg[:300],
        }

    if 'appgate' in index:
        return {
            'timestamp': ts, 'index': index, 'type': 'appgate',
            'message':  src.get('message', '')[:300],
            'hostname': src.get('hostname', ''),
            'level':    src.get('log_level', src.get('level', '')),
            'src_ip':   src.get('clientIp', src.get('src_ip', '')),
            'action':   src.get('action', ''),
        }

    if 'security' in index:
        return {
            'timestamp':   ts, 'index': index, 'type': 'security',
            'message':     src.get('message', '')[:300],
            'device_type': src.get('device_type', ''),
            'log_type':    src.get('log_type', ''),
        }

    return {
        'timestamp': ts, 'index': index, 'type': 'generic',
        'message':   src.get('message', str(src))[:300],
    }


# ── RAG context retrieval ──────────────────────────────────────────────────────
def retrieve_rag_context(client, logs: List[Dict]) -> str:
    """Search knowledge-base index for context relevant to current logs."""
    if not ENABLE_RAG or not logs:
        return ''

    sample = ' '.join(
        log.get('message') or log.get('raw', '')
        for log in logs[:30]
        if log.get('message') or log.get('raw')
    )[:2000]

    try:
        from rag_module import RAGManager
        rag = RAGManager(
            opensearch_endpoint=OPENSEARCH_ENDPOINT,
            ollama_url=OLLAMA_BASE_URL,
            embedding_model=EMBED_MODEL,
            region=AWS_REGION,
            index_name=RAG_INDEX
        )
        chunks = rag.search_similar(sample, k=RAG_K, min_score=0.3)

        if not chunks:
            print("  ⚠  RAG: 0 chunks matched (knowledge-base may need more docs)")
            return ''

        context = '\n\nRELEVANT RUNBOOK DOCUMENTATION:\n'
        for chunk in chunks:
            source = Path(chunk['source']).name
            context += f'\n[{source}] (relevance: {chunk["score"]:.2f})\n{chunk["text"]}\n'
        print(f"  ✓ RAG: {len(chunks)} chunks retrieved")
        return context

    except Exception as e:
        print(f"  ⚠  RAG retrieval failed: {e}")
        return ''


# ── Analysis ───────────────────────────────────────────────────────────────────
def analyze_logs(logs: List[Dict], rag_context: str = '') -> str:
    """Send logs + RAG context to Ollama. Returns analysis string."""
    if not logs:
        return 'No logs available for analysis.'

    # IP correlation across sources
    appgate_ips = {l.get('src_ip', '') for l in logs if l.get('type') == 'appgate'}
    palo_ips    = {l.get('src_ip', '') for l in logs if l.get('type') == 'palo_alto'}
    correlated  = sorted((appgate_ips & palo_ips) - {''})

    by_type = {}
    for log in logs:
        t = log.get('type', 'generic')
        by_type[t] = by_type.get(t, 0) + 1

    prompt = f"""You are a SOC Analyst for a DoD IL6 environment (AWS GovCloud).
Analyze the following security logs and produce a structured intelligence report.

LOG SUMMARY:
- Total events: {len(logs)}
- By source: {json.dumps(by_type)}
- Correlated IPs (present in both AppGate + Palo Alto): {correlated}
{rag_context}

LOG DATA (up to 100 events):
{json.dumps(logs[:100], default=str, indent=2)}

Provide a structured markdown report with these sections:
1. Executive Summary
2. Critical Issues (if any)
3. AppGate SDP Analysis (access patterns, denied attempts, anomalies)
4. Palo Alto Firewall Analysis (traffic anomalies, blocked traffic, rule hits)
5. Security Events
6. Correlated Threat Indicators (IPs appearing in multiple sources)
7. Patterns & Trends
8. Recommendations
9. Runbook References (if documentation context was provided)

Be specific and actionable. Prioritize what the operations team needs right now."""

    try:
        r = requests.post(
            f'{OLLAMA_BASE_URL}/api/generate',
            json={'model': MODEL_NAME, 'prompt': prompt, 'stream': False},
            timeout=600
        )
        r.raise_for_status()
        return r.json().get('response', 'No response from model.')
    except Exception as e:
        return f'Analysis failed: {e}'


# ── Report saving ──────────────────────────────────────────────────────────────
def save_report(analysis: str, logs: List[Dict], rag_context: str) -> Path:
    """Persist analysis as JSON + TXT in OUTPUT_DIR."""
    ts    = datetime.now(timezone.utc)
    stamp = ts.strftime('%Y%m%d_%H%M%S')

    by_index = {}
    for log in logs:
        idx = log.get('index', 'unknown')
        by_index[idx] = by_index.get(idx, 0) + 1

    data = {
        'generated':     ts.isoformat(),
        'model':         MODEL_NAME,
        'analysis_type': 'general',
        'rag_enabled':   ENABLE_RAG and bool(rag_context),
        'log_lines':     len(logs),
        'analysis':      analysis,
        'metadata': {
            'by_index':   by_index,
            'total_logs': len(logs),
            'rag_context': bool(rag_context),
        }
    }

    base = OUTPUT_DIR / f'analysis_rag_{stamp}'
    with open(f'{base}.json', 'w') as f:
        json.dump(data, f, indent=2, default=str)
    with open(f'{base}.txt', 'w') as f:
        f.write(f'Generated : {ts.isoformat()}\n')
        f.write(f'Model     : {MODEL_NAME}\n')
        f.write(f'RAG       : {"On" if data["rag_enabled"] else "Off"}\n')
        f.write(f'Log count : {len(logs)}\n\n')
        f.write(analysis)

    print(f'  💾 Saved: analysis_rag_{stamp}.json')
    return base


# ── Single analysis cycle ──────────────────────────────────────────────────────
def run_cycle():
    """Run one complete fetch → RAG → analyze → save cycle."""
    print(f'\n--- {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")} ---')
    client = get_opensearch_client()

    print('🔍 Fetching logs...')
    logs = fetch_logs(client)
    if not logs:
        print('⚠  No logs found — check TIME_RANGE_MINUTES and index patterns')
        return

    print('📚 Retrieving RAG context...')
    rag_context = retrieve_rag_context(client, logs)

    print(f'🤖 Analyzing with {MODEL_NAME}...')
    analysis = analyze_logs(logs, rag_context)

    save_report(analysis, logs, rag_context)
    print('✅ Cycle complete')


# ── Entrypoint ─────────────────────────────────────────────────────────────────
def main():
    import sys
    print('\n=== IL6 RAG Log Analyst ===')
    print(f'Model   : {MODEL_NAME}')
    print(f'Indices : {OPENSEARCH_INDEX}')
    print(f'RAG     : {"enabled" if ENABLE_RAG else "disabled"}')

    if '--once' in sys.argv:
        run_cycle()
        return

    if WATCH_MODE:
        print(f'Watch mode: every {WATCH_INTERVAL} min\n')
        while True:
            try:
                run_cycle()
            except Exception as e:
                print(f'⚠  Cycle error: {e}')
            time.sleep(WATCH_INTERVAL * 60)
    else:
        run_cycle()


if __name__ == '__main__':
    main()
PYEOF

echo "   ✓ main_rag.py written ($(wc -l < "$TARGET") lines)"

# ── 3. Rebuild the agent container ────────────────────────────────────────────
echo ""
echo "🔨 Rebuilding log-analyst-rag container..."
sudo docker compose -f "$COMPOSE_FILE" build log-analyst-rag

# ── 4. Restart only the agent (leave ollama/dashboard/open-webui running) ─────
echo ""
echo "🔄 Restarting log-analyst-rag..."
sudo docker compose -f "$COMPOSE_FILE" up -d log-analyst-rag

# ── 5. Wait for container to initialize ───────────────────────────────────────
echo ""
echo "⏳ Waiting 10 seconds for startup..."
sleep 10

# ── 6. Verify all containers still healthy ────────────────────────────────────
echo ""
echo "📋 Container status:"
sudo docker compose -f "$COMPOSE_FILE" ps

# ── 7. Tail logs ──────────────────────────────────────────────────────────────
echo ""
echo "📡 Tailing log-analyst-rag logs (Ctrl+C to stop)..."
echo "   Watching for: ✓ Connected to OpenSearch → 🔍 Fetching → 🤖 Analyzing → ✅ Done"
echo "──────────────────────────────────────────────────────────────────"
sudo docker logs -f log-analyst-rag

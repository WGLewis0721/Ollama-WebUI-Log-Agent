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
        chunks = rag.search_similar(sample, k=RAG_K, min_score=0.0)

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
def analyze_logs(logs: List[Dict], rag_context: str = '', user_query: str = '') -> str:
    """Send logs + RAG context to Ollama via /api/chat for proper instruction following."""
    if not logs:
        return 'No logs available for analysis.'

    appgate_ips = {l.get('src_ip', '') for l in logs if l.get('type') == 'appgate'}
    palo_ips    = {l.get('src_ip', '') for l in logs if l.get('type') == 'palo_alto'}
    correlated  = sorted((appgate_ips & palo_ips) - {''})
    by_type = {}
    for log in logs:
        t = log.get('type', 'generic')
        by_type[t] = by_type.get(t, 0) + 1

    # Pre-extract facts in Python so the model gets answers not raw JSON
    timestamps  = sorted([l.get('timestamp','') for l in logs if l.get('timestamp')], reverse=True)
    most_recent = timestamps[0] if timestamps else 'NOT FOUND'
    oldest      = timestamps[-1] if timestamps else 'NOT FOUND'

    src_counts = {}
    dst_counts = {}
    rules      = set()
    actions    = set()
    for l in logs:
        s = l.get('src_ip','')
        if s: src_counts[s] = src_counts.get(s,0)+1
        d = l.get('dst_ip','')
        if d: dst_counts[d] = dst_counts.get(d,0)+1
        r = l.get('rule','')
        if r: rules.add(r)
        a = l.get('action','')
        if a: actions.add(a)

    top_src = sorted(src_counts.items(), key=lambda x: x[1], reverse=True)[:5] if src_counts else []
    top_dst = sorted(dst_counts.items(), key=lambda x: x[1], reverse=True)[:5] if dst_counts else []

    log_context = f"""EXTRACTED FACTS (pre-computed from {len(logs)} log entries):
- Most recent timestamp : {most_recent}
- Oldest timestamp      : {oldest}
- Total log count       : {len(logs)}
- Log sources           : {json.dumps(by_type)}
- Correlated IPs        : {correlated}
- Unique firewall rules : {sorted(rules)}
- Unique actions        : {sorted(actions)}
- Top source IPs        : {top_src}
- Top destination IPs   : {top_dst}
- Indices present       : {sorted(set(l.get('index','') for l in logs if l.get('index')))}
{rag_context}
SAMPLE RAW LOGS (5 most recent for reference only):
{json.dumps(logs[:5], default=str, indent=None)}"""

    # System role — defines WHO the model is
    system_msg = """You are a SOC Analyst for a DoD IL6 classified environment (AWS GovCloud).
You have access to real security logs from Palo Alto NGFW and AppGate SDP.
Rules:
- Answer ONLY from the log data provided. Never invent IPs, rule names, timestamps, or counts.
- If data is not in the logs, say: NOT FOUND IN LOGS
- If the user asks a direct question, answer it directly. Do not generate a full report unless asked.
- If the user specifies a format (Q1: Q2: Q3: or a table), use that exact format.
- Never fabricate runbook URLs. Only reference runbook content that was explicitly provided."""

    # User role — the actual question + data
    if user_query and len(user_query.strip()) > 10:
        user_msg = f"""{user_query}

Here is the log data to answer from:
{log_context}"""
    else:
        user_msg = f"""Analyze the following security logs and produce a structured report with these sections:
1. Executive Summary
2. Critical Issues
3. AppGate SDP Analysis
4. Palo Alto Firewall Analysis
5. Security Events (table format)
6. Correlated Threat Indicators
7. Patterns & Trends
8. Recommendations
9. Runbook References (only if runbook content was provided above)

{log_context}"""

    try:
        r = requests.post(
            f'{OLLAMA_BASE_URL}/api/chat',
            json={
                'model': MODEL_NAME,
                'messages': [
                    {'role': 'system',  'content': system_msg},
                    {'role': 'user',    'content': user_msg}
                ],
                'stream': False
            },
            timeout=600
        )
        r.raise_for_status()
        return r.json().get('message', {}).get('content', 'No response from model.')
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

#!/bin/bash
# =============================================================================
# phase3_rag_validation.sh — CNAP Log Analyst Agent
# Phase 3: Prove docs are uploaded, chunked, indexed, retrievable, and used
# Run from: /home/ubuntu/log-analyst-agent
# Usage:    bash phase3_rag_validation.sh | tee phase3_output.txt
# =============================================================================

PROJECT="/home/ubuntu/log-analyst-agent"
COMPOSE_FILE="$PROJECT/docker-compose-rag.yml"
AGENT="$PROJECT/agent"

DIVIDER="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
HDR() { echo ""; echo "$DIVIDER"; echo "  $1"; echo "$DIVIDER"; }
PASS() { echo "  ✅ PASS: $1"; }
FAIL() { echo "  ❌ FAIL: $1"; }
WARN() { echo "  ⚠️  WARN: $1"; }

HDR "PHASE 3 — RAG VALIDATION"
echo "  Goal: prove docs are uploaded, chunked, indexed, retrievable, and used in output"
echo "  Time: ~3-5 minutes (includes one live analysis with RAG)"

# ── 3.1 S3 bucket — what docs exist ──────────────────────────────────────────
HDR "3.1 · S3 KNOWLEDGE BASE — what docs are uploaded"
sudo docker exec log-analyst-rag python3 -c "
import os, boto3
bucket = os.getenv('S3_KNOWLEDGE_BASE_BUCKET', '')
region = os.getenv('AWS_REGION', 'us-gov-west-1')
if not bucket:
    print('S3_KNOWLEDGE_BASE_BUCKET not set in env')
    exit()
s3 = boto3.client('s3', region_name=region)
try:
    paginator = s3.get_paginator('list_objects_v2')
    total = 0
    for page in paginator.paginate(Bucket=bucket, Prefix='knowledge-base/'):
        for obj in page.get('Contents', []):
            size_kb = obj['Size'] // 1024
            print(f'  {obj[\"Key\"]:60s}  {size_kb:>4} KB  {obj[\"LastModified\"].strftime(\"%Y-%m-%d\")}')
            total += 1
    print(f'  Total: {total} file(s)')
except Exception as e:
    print(f'S3 list failed: {e}')
" 2>/dev/null || FAIL "Could not exec into log-analyst-rag"

# ── 3.2 OpenSearch knowledge-base index — chunk count and samples ─────────────
HDR "3.2 · OPENSEARCH knowledge-base — chunk count and content"
sudo docker exec log-analyst-rag python3 -c "
import os
from opensearch_integration import OpenSearchLogFetcher

c = OpenSearchLogFetcher(os.environ['OPENSEARCH_ENDPOINT'], os.environ['AWS_REGION'])
try:
    count = c.client.count(index='knowledge-base')['count']
    print(f'  Total chunks indexed: {count}')
    if count == 0:
        print('  ❌ FAIL: 0 chunks — indexer has not been run or docs not uploaded')
    else:
        print(f'  ✅ PASS: {count} chunks in knowledge-base index')
        # Show sample chunks
        r = c.client.search(index='knowledge-base', body={
            'size': 5,
            'query': {'match_all': {}},
            '_source': ['source', 'text', 'chunk_index']
        })
        print()
        print('  Sample chunks:')
        for h in r['hits']['hits']:
            src = h['_source']
            print(f'    source     : {src.get(\"source\",\"?\"):50s}')
            print(f'    chunk_index: {src.get(\"chunk_index\",\"?\")}')
            print(f'    text[:120] : {src.get(\"text\",\"\")[:120].strip()}')
            print()
except Exception as e:
    print(f'  ❌ FAIL: {e}')
" 2>/dev/null

# ── 3.3 Embedding model available ────────────────────────────────────────────
HDR "3.3 · EMBEDDING MODEL — nomic-embed-text available in Ollama"
sudo docker exec log-analyst-rag python3 -c "
import requests
r = requests.get('http://ollama:11434/api/tags', timeout=5)
models = [m['name'] for m in r.json().get('models', [])]
print('  Models available:', models)
if any('nomic-embed-text' in m for m in models):
    print('  ✅ PASS: nomic-embed-text is loaded')
else:
    print('  ❌ FAIL: nomic-embed-text NOT found — run: ollama pull nomic-embed-text')
" 2>/dev/null

# ── 3.4 kNN search — can RAG actually retrieve chunks ─────────────────────────
HDR "3.4 · kNN RETRIEVAL — simulate RAG search with real log sample"
sudo docker exec log-analyst-rag python3 -c "
import os
from opensearch_integration import OpenSearchLogFetcher
from rag_module import RAGManager

c = OpenSearchLogFetcher(os.environ['OPENSEARCH_ENDPOINT'], os.environ['AWS_REGION'])

# Pull a real log sample to build the query
logs = c.fetch_logs(index_pattern='cwl-*', time_range_minutes=99999, max_logs=10)
if not logs:
    print('  ⚠️  No logs to build query from — using static test query')
    query_text = 'Palo Alto firewall denied traffic blocked rule AppGate access denied'
else:
    sample = [l.get('@message', l.get('message', '')) for l in logs[:5]]
    query_text = ' '.join(str(s)[:100] for s in sample if s)
    print(f'  Query built from {len(logs)} real logs')
    print(f'  Query preview: {query_text[:150]}')

print()
rag = RAGManager(
    opensearch_endpoint=os.environ['OPENSEARCH_ENDPOINT'],
    ollama_url='http://ollama:11434',
    embedding_model='nomic-embed-text',
    region=os.environ['AWS_REGION'],
    index_name='knowledge-base'
)

chunks = rag.search_similar(query_text, k=3, min_score=0.0)
print(f'  Chunks retrieved (min_score=0.0): {len(chunks)}')
if chunks:
    print('  ✅ PASS: RAG retrieval working')
    print()
    for i, chunk in enumerate(chunks, 1):
        import pathlib
        print(f'  [{i}] source : {pathlib.Path(chunk[\"source\"]).name}')
        print(f'      score  : {chunk[\"score\"]:.4f}')
        print(f'      text   : {chunk[\"text\"][:200].strip()}')
        print()
else:
    print('  ❌ FAIL: No chunks returned — check embedding model and index mapping')
" 2>/dev/null

# ── 3.5 End-to-end RAG injection — prove context appears in analysis ──────────
HDR "3.5 · END-TO-END — prove RAG context is injected into analysis output"
echo "  Sending request to /v1/chat/completions and checking for RAG usage..."
echo "  (This takes 30-60 seconds)"
echo ""

RESPONSE=$(curl -s -X POST http://localhost:7000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Analyze logs. Reference any runbook documentation you find."}]}' \
  --max-time 300)

python3 -c "
import json, sys

response = '''$RESPONSE'''
try:
    d = json.loads(response)
    content = d['choices'][0]['message']['content']
    meta    = d.get('metadata', {})

    print(f'  Log count : {meta.get(\"log_count\", \"?\")}')
    print(f'  RAG used  : {meta.get(\"rag_used\", \"?\")}')
    print(f'  Length    : {len(content)} chars')
    print()

    if meta.get('rag_used'):
        print('  ✅ PASS: RAG context was retrieved and injected into prompt')
    else:
        print('  ❌ FAIL: RAG not used — knowledge-base may have 0 matching chunks')
        print('          Action: upload more docs to S3 and re-run the indexer')

    # Check if analysis references runbook content
    keywords = ['runbook', 'documentation', 'reference', 'according to', 'procedure', 'playbook']
    found = [k for k in keywords if k.lower() in content.lower()]
    if found:
        print(f'  ✅ PASS: Analysis references runbook content ({found})')
    else:
        print('  ⚠️  WARN: Analysis does not explicitly reference runbook content')

    print()
    print('  Analysis preview (first 600 chars):')
    print('  ' + content[:600].replace('\n', '\n  '))
except Exception as e:
    print(f'  ❌ FAIL: Could not parse response: {e}')
    print(f'  Raw: {response[:300]}')
"

# ── 3.6 If RAG failed — run the indexer to fix it ────────────────────────────
HDR "3.6 · INDEXER — re-run if chunk count is low"
CHUNK_COUNT=$(sudo docker exec log-analyst-rag python3 -c "
import os
from opensearch_integration import OpenSearchLogFetcher
c = OpenSearchLogFetcher(os.environ['OPENSEARCH_ENDPOINT'], os.environ['AWS_REGION'])
try:
    print(c.client.count(index='knowledge-base')['count'])
except:
    print(0)
" 2>/dev/null)

echo "  Current chunk count: $CHUNK_COUNT"

if [ "$CHUNK_COUNT" -lt 10 ] 2>/dev/null; then
    WARN "Only $CHUNK_COUNT chunks — running indexer now to pull from S3..."
    sudo docker compose -f "$COMPOSE_FILE" --profile tools run --rm indexer 2>&1 | tail -20
    NEW_COUNT=$(sudo docker exec log-analyst-rag python3 -c "
import os
from opensearch_integration import OpenSearchLogFetcher
c = OpenSearchLogFetcher(os.environ['OPENSEARCH_ENDPOINT'], os.environ['AWS_REGION'])
try:
    print(c.client.count(index='knowledge-base')['count'])
except:
    print(0)
" 2>/dev/null)
    echo "  Chunk count after indexing: $NEW_COUNT"
    if [ "$NEW_COUNT" -gt "$CHUNK_COUNT" ] 2>/dev/null; then
        PASS "Indexer added chunks — re-run this script to validate RAG"
    else
        FAIL "Chunk count unchanged — check S3_KNOWLEDGE_BASE_BUCKET and S3 prefix"
        echo "  Upload docs to S3 with:"
        echo "    aws s3 cp your-runbook.md s3://\$S3_KNOWLEDGE_BASE_BUCKET/knowledge-base/runbooks/ --region us-gov-west-1"
    fi
else
    PASS "$CHUNK_COUNT chunks present — sufficient for RAG"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
HDR "PHASE 3 SUMMARY"
echo "  Check the PASS/FAIL/WARN lines above."
echo ""
echo "  If RAG used = False:"
echo "    1. Upload .md/.txt runbooks to S3 knowledge-base/ prefix"
echo "    2. Run: sudo docker compose -f docker-compose-rag.yml --profile tools run --rm indexer"
echo "    3. Re-run this script"
echo ""
echo "  If all PASS → proceed to Phase 4 (OpenWebUI validation)"
echo ""

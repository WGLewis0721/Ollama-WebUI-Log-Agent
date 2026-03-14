#!/usr/bin/env python3
"""
RAG Indexer - Populates existing knowledge-base index in OpenSearch
Matches schema: text, embedding (768-dim), source, chunk_id, 
                chunk_index, metadata, timestamp, path, doc_id
"""

import os
import json
import sys
import hashlib
import boto3
import requests
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth

S3_BUCKET         = os.getenv('S3_BUCKET_NAME', 'cnap-dev-il6-ollama-knowledge-base-wgl')
S3_PREFIX         = os.getenv('S3_PREFIX', 'knowledge/base')
OPENSEARCH_HOST   = os.getenv('OPENSEARCH_ENDPOINT', '')
AWS_REGION        = os.getenv('AWS_REGION', 'us-gov-west-1')
OLLAMA_URL        = os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434')
RAG_INDEX         = 'knowledge-base'
EMBED_MODEL       = 'nomic-embed-text'
CHUNK_SIZE        = 400
CHUNK_OVERLAP     = 80


def get_client():
    session     = boto3.Session()
    creds       = session.get_credentials()
    awsauth     = AWS4Auth(
        creds.access_key, creds.secret_key,
        AWS_REGION, 'es', session_token=creds.token
    )
    return OpenSearch(
        hosts=[{'host': OPENSEARCH_HOST, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )


def get_embedding(text):
    try:
        r = requests.post(
            f'{OLLAMA_URL}/api/embeddings',
            json={'model': EMBED_MODEL, 'prompt': text[:2000]},
            timeout=60
        )
        if r.status_code == 200:
            return r.json().get('embedding', [])
    except Exception as e:
        print(f"    ⚠ Embedding error: {e}")
    return []


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks by word count"""
    words   = text.split()
    chunks  = []
    i       = 0
    while i < len(words):
        chunk = words[i:i + size]
        chunks.append(' '.join(chunk))
        i += size - overlap
    return chunks


def index_documents(client):
    s3        = boto3.client('s3', region_name=AWS_REGION)
    paginator = s3.get_paginator('list_objects_v2')
    pages     = paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_PREFIX)

    total_docs   = 0
    total_chunks = 0

    for page in pages:
        if 'Contents' not in page:
            print("  ⚠ No documents found in S3")
            return 0, 0

        for obj in page['Contents']:
            key = obj['Key']
            if key.endswith('/'):
                continue
            ext = key.split('.')[-1].lower()
            if ext not in ['txt', 'md', 'json', 'log', 'yaml', 'yml']:
                print(f"  ⏭  Skipping {key}")
                continue

            print(f"\n  📄 {key}")

            # Download
            body    = s3.get_object(Bucket=S3_BUCKET, Key=key)['Body']
            content = body.read().decode('utf-8', errors='ignore')
            doc_id  = hashlib.md5(content.encode()).hexdigest()

            # Check if already indexed
            try:
                result = client.search(
                    index=RAG_INDEX,
                    body={'query': {'term': {'doc_id': doc_id}}, 'size': 1}
                )
                if result['hits']['total']['value'] > 0:
                    print(f"     ⏭  Already indexed ({doc_id[:8]}...)")
                    total_docs += 1
                    continue
            except Exception:
                pass

            # Chunk
            chunks = chunk_text(content)
            print(f"     → {len(chunks)} chunks")

            # Index each chunk
            actions = []
            for i, chunk in enumerate(chunks):
                print(f"     → Embedding {i+1}/{len(chunks)}...", end='\r')
                embedding = get_embedding(chunk)
                if not embedding:
                    continue

                actions.append({
                    '_index': RAG_INDEX,
                    '_id':    f"{doc_id}_{i}",
                    '_source': {
                        'text':        chunk,
                        'embedding':   embedding,
                        'source':      f"s3://{S3_BUCKET}/{key}",
                        'path':        key,
                        'doc_id':      doc_id,
                        'chunk_id':    f"{doc_id}_{i}",
                        'chunk_index': i,
                        'timestamp':   datetime.utcnow().isoformat(),
                        'metadata': {
                            'extension':    ext,
                            'size':         obj['Size'],
                            'last_modified': obj['LastModified'].isoformat()
                        }
                    }
                })

            # Bulk index
            if actions:
                helpers.bulk(client, actions)
                total_chunks += len(actions)
                print(f"     ✓ Indexed {len(actions)} chunks        ")

            total_docs += 1

    return total_docs, total_chunks


def show_stats(client):
    try:
        count = client.count(index=RAG_INDEX)['count']
        print(f"\n📊 knowledge-base index:")
        print(f"   Total chunks: {count}")

        agg = client.search(index=RAG_INDEX, body={
            'size': 0,
            'aggs': {'paths': {'terms': {'field': 'path', 'size': 50}}}
        })
        print(f"   Documents:")
        for b in agg['aggregations']['paths']['buckets']:
            print(f"     {b['key']}: {b['doc_count']} chunks")
    except Exception as e:
        print(f"  ⚠ Stats error: {e}")


def test_search(client, query):
    print(f"\n🔍 Searching: '{query}'")
    embedding = get_embedding(query)
    if not embedding:
        print("  ⚠ Could not generate embedding")
        return

    results = client.search(index=RAG_INDEX, body={
        'size': 3,
        'query': {'knn': {'embedding': {'vector': embedding, 'k': 3}}},
        '_source': ['text', 'path', 'chunk_index']
    })

    for i, hit in enumerate(results['hits']['hits'], 1):
        s = hit['_source']
        print(f"\n  Result {i} (score: {hit['_score']:.3f})")
        print(f"  Path: {s.get('path','?')}")
        print(f"  Text: {s.get('text','')[:200]}...")


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'index'

    print(f"\n{'='*60}")
    print(f"📚 RAG Indexer")
    print(f"{'='*60}")
    print(f"  S3:    s3://{S3_BUCKET}/{S3_PREFIX}")
    print(f"  OS:    {OPENSEARCH_HOST[:50]}...")
    print(f"  Index: {RAG_INDEX}")
    print(f"{'='*60}\n")

    client = get_client()
    print("✓ Connected to OpenSearch")

    if cmd == 'index':
        print(f"\n📥 Indexing documents from S3...\n")
        docs, chunks = index_documents(client)
        print(f"\n✅ Done: {docs} documents, {chunks} chunks indexed")
        show_stats(client)

    elif cmd == 'stats':
        show_stats(client)

    elif cmd == 'test':
        query = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else 'authentication failure'
        test_search(client, query)

    elif cmd == 'clear':
        confirm = input(f"Delete all docs from '{RAG_INDEX}'? (yes/no): ")
        if confirm == 'yes':
            client.delete_by_query(
                index=RAG_INDEX,
                body={'query': {'match_all': {}}}
            )
            print(f"✓ Cleared {RAG_INDEX}")


if __name__ == '__main__':
    main()

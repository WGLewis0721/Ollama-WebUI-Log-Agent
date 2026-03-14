#!/usr/bin/env python3
"""
api_server.py — OpenAI-compatible API server for the CNAP Log Analyst Agent
v3: Dual-mode routing
  - Query mode  : specific question → LLM generates OpenSearch DSL → execute → explain
  - Report mode : generic request  → fetch 315 logs → RAG → full SOC report

Endpoints:
  GET  /v1/models
  POST /v1/chat/completions
  GET  /health
  GET  /v1/latest_query   ← new: returns last query result for dashboard polling
"""

import os
import json
import time
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pathlib import Path

from main_rag import (
    get_opensearch_client,
    fetch_logs,
    retrieve_rag_context,
    analyze_logs
)
from query_generator import generate_opensearch_query, is_specific_question
from opensearch_executor import run_query, format_results_for_llm, summarize_for_dashboard

import requests as http_requests

app = FastAPI(title="CNAP Log Analyst API", version="3.0")

# ── Config ────────────────────────────────────────────────────────────────────
OPENSEARCH_INDEX   = os.getenv("OPENSEARCH_INDEX", "cwl-*,appgate-logs-*,security-logs-*")
TIME_RANGE_MINUTES = int(os.getenv("TIME_RANGE_MINUTES", "99999"))
MODEL_NAME         = os.getenv("MODEL_NAME", "llama3.1:8b")
OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
OUTPUT_DIR         = Path(os.getenv("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

LATEST_QUERY_FILE  = OUTPUT_DIR / "latest_query.json"


# ── Helpers ───────────────────────────────────────────────────────────────────
def explain_results(user_question: str, formatted_results: str, rag_context: str = "") -> str:
    """Send OpenSearch results to llama3.1:8b for explanation."""
    system = """You are a SOC Analyst for a DoD IL6 classified environment.
You are explaining OpenSearch query results to an analyst.
Rules:
- Be direct and specific. Lead with the most important finding.
- Use exact numbers, IPs, timestamps, and rule names from the results.
- Do NOT invent data. If something is not in the results, say so.
- Keep responses concise — 3 to 8 sentences for simple questions, longer for complex ones.
- If runbook context is provided, reference relevant procedures."""

    user_msg = f"""Question: {user_question}

OpenSearch Results:
{formatted_results}
"""
    if rag_context:
        user_msg += f"\nRunbook Context:\n{rag_context}\n"

    user_msg += "\nAnswer the analyst's question based on these results:"

    try:
        r = http_requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_msg}
                ],
                "stream": False
            },
            timeout=300
        )
        r.raise_for_status()
        return r.json().get("message", {}).get("content", "No response from model.")
    except Exception as e:
        return f"Explanation failed: {e}"


def build_openai_response(content: str, model: str, metadata: dict) -> dict:
    """Wrap response in OpenAI-compatible envelope."""
    return {
        "object":  "chat.completion",
        "model":   model,
        "choices": [{
            "index":         0,
            "message":       {"role": "assistant", "content": content},
            "finish_reason": "stop"
        }],
        "metadata": metadata
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{
            "id":          "log-analyst-rag",
            "object":      "model",
            "created":     int(time.time()),
            "owned_by":    "cnap-devsecops",
            "description": "IL6 RAG Log Analyst — OpenSearch + Ollama + RAG (dual-mode)"
        }]
    }


@app.post("/v1/chat/completions")
async def chat(request: Request):
    body     = await request.json()
    messages = body.get("messages", [])
    query    = messages[-1]["content"] if messages else ""

    print(f"\n[API v3] Request: {query[:100]}")

    # ── Connect to OpenSearch ──────────────────────────────────────────────────
    try:
        client = get_opensearch_client()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"OpenSearch connection failed: {e}"})

    # ── Route: query mode vs report mode ──────────────────────────────────────
    if is_specific_question(query):
        print("[API v3] MODE: query — generating OpenSearch DSL")

        # Step 1 — Generate query
        generated_query = generate_opensearch_query(query)
        print(f"  Generated DSL: {json.dumps(generated_query)[:150]}")

        # Step 2 — Execute query
        raw_result = run_query(client, generated_query, index=OPENSEARCH_INDEX)

        # Step 3 — RAG context
        rag_context = ""
        try:
            dummy_logs  = [{"message": query, "type": "generic"}]
            rag_context = retrieve_rag_context(client, dummy_logs)
        except Exception:
            pass

        # Step 4 — Format results for LLM
        formatted = format_results_for_llm(raw_result, max_hits=15)
        print(f"  Formatted results preview: {formatted[:200]}")

        # Step 5 — Explain results
        explanation = explain_results(query, formatted, rag_context)

        # Step 6 — Save to dashboard file
        dashboard_payload = summarize_for_dashboard(
            user_question  = query,
            generated_query= generated_query,
            query_result   = raw_result,
            explanation    = explanation
        )
        try:
            LATEST_QUERY_FILE.write_text(json.dumps(dashboard_payload, indent=2, default=str))
            print(f"  Dashboard payload saved → {LATEST_QUERY_FILE}")
        except Exception as e:
            print(f"  WARN: Could not save dashboard payload: {e}")

        total_hits = raw_result.get("hits", {}).get("total", {})
        hit_count  = total_hits.get("value", 0) if isinstance(total_hits, dict) else total_hits

        # Build user-visible response with query visible for verification
        has_aggs = bool(raw_result.get("aggregations"))
        response_content = explanation
        response_content += f"\n\n---\n**OpenSearch Query Used** *(verify in Dev Tools → POST /{OPENSEARCH_INDEX}/_search)*\n```json\n{json.dumps(generated_query, indent=2)}\n```"

        return build_openai_response(
            content  = response_content,
            model    = "log-analyst-rag",
            metadata = {
                "mode":          "query",
                "hit_count":     hit_count,
                "has_aggs":      has_aggs,
                "rag_used":      bool(rag_context),
                "indices":       OPENSEARCH_INDEX,
                "model":         MODEL_NAME,
                "dashboard_url": "http://localhost:5000/latest_query"
            }
        )

    else:
        # ── Report mode — existing RAG + batch analysis ────────────────────────
        print("[API v3] MODE: report — fetching logs for full analysis")

        logs = fetch_logs(client, OPENSEARCH_INDEX, TIME_RANGE_MINUTES)
        if not logs:
            return build_openai_response(
                content  = (
                    f"⚠️ No logs found in OpenSearch.\n\n"
                    f"**Indices:** `{OPENSEARCH_INDEX}`\n"
                    f"**Time range:** last {TIME_RANGE_MINUTES} minutes\n\n"
                    "Check that Fluent Bit is forwarding logs and index patterns match."
                ),
                model    = "log-analyst-rag",
                metadata = {"mode": "report", "log_count": 0, "rag_used": False}
            )

        print(f"[API v3] Fetched {len(logs)} logs")

        rag_context = retrieve_rag_context(client, logs)
        rag_used    = bool(rag_context)
        print(f"[API v3] RAG: {'retrieved' if rag_used else 'none'}")

        answer = analyze_logs(logs, rag_context, user_query=query)

        return build_openai_response(
            content  = answer,
            model    = "log-analyst-rag",
            metadata = {
                "mode":      "report",
                "log_count": len(logs),
                "rag_used":  rag_used,
                "indices":   OPENSEARCH_INDEX,
                "model":     MODEL_NAME
            }
        )


@app.get("/v1/latest_query")
async def latest_query():
    """Return the most recent query-mode result for dashboard polling."""
    try:
        data = json.loads(LATEST_QUERY_FILE.read_text())
        return JSONResponse(content=data)
    except FileNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"error": "No query results yet — send a specific question first"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
async def health():
    return {"status": "ok", "service": "log-analyst-rag", "version": "3.0", "model": MODEL_NAME}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7000)


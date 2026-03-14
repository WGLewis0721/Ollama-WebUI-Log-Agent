#!/usr/bin/env python3
"""
opensearch_executor.py — Execute LLM-generated OpenSearch queries and format results.
Handles both hits-based and aggregation-based responses.
"""

import json
import os
from typing import Dict, Any, Tuple

INDICES = os.getenv("OPENSEARCH_INDEX", "cwl-*,appgate-logs-*,security-logs-*")


def run_query(client, query: dict, index: str = None) -> dict:
    """
    Execute an OpenSearch query and return the raw response.
    Catches and surfaces errors cleanly.
    """
    target_index = index or INDICES
    try:
        # client may be an OpenSearchLogFetcher wrapper — unwrap if needed
        os_client = getattr(client, 'client', client)
        # Accept both dict and JSON string
        if isinstance(query, str):
            import json as _json
            query = _json.loads(query)
        # Fix _doc_count -> _count in any agg order
        import json as _json2
        q_str = _json2.dumps(query).replace('_doc_count', '_count')
        query = _json2.loads(q_str)
        result = os_client.search(
            index=target_index,
            body=query,
            ignore_unavailable=True
        )
        total = result.get("hits", {}).get("total", {})
        count = total.get("value", 0) if isinstance(total, dict) else total
        has_aggs = bool(result.get("aggregations"))
        print(f"  [Executor] Query returned {count} hits, aggs={has_aggs}")
        return result
    except Exception as e:
        print(f"  [Executor] ERROR: {e}")
        return {"error": str(e), "hits": {"hits": [], "total": {"value": 0}}}


def format_results_for_llm(query_result: dict, max_hits: int = 15) -> str:
    """
    Convert raw OpenSearch response into a compact, LLM-readable summary.
    Handles both hits and aggregations.
    """
    if "error" in query_result:
        return f"Query failed: {query_result['error']}"

    lines = []
    total = query_result.get("hits", {}).get("total", {})
    count = total.get("value", 0) if isinstance(total, dict) else total
    lines.append(f"Total matching documents: {count}")

    # Handle aggregations
    aggs = query_result.get("aggregations", {})
    if aggs:
        lines.append("\nAGGREGATION RESULTS:")
        for agg_name, agg_data in aggs.items():
            lines.append(f"\n{agg_name}:")
            buckets = agg_data.get("buckets", [])
            if buckets:
                for b in buckets[:20]:
                    key   = b.get("key_as_string") or b.get("key", "?")
                    count = b.get("doc_count", 0)
                    lines.append(f"  {key}: {count} events")
            else:
                # Scalar aggregation (sum, avg, max, min)
                val = agg_data.get("value")
                if val is not None:
                    lines.append(f"  value: {val}")

    # Handle hits
    hits = query_result.get("hits", {}).get("hits", [])
    if hits:
        lines.append(f"\nSAMPLE RESULTS (up to {max_hits}):")
        for h in hits[:max_hits]:
            src = h.get("_source", {})
            # Extract the most useful fields regardless of index type
            ts      = src.get("@timestamp", src.get("timestamp", ""))
            msg     = src.get("@message", src.get("message", ""))
            src_ip  = src.get("src_ip", src.get("clientIp", ""))
            dst_ip  = src.get("dst_ip", "")
            rule    = src.get("rule", src.get("policyName", ""))
            action  = src.get("action", "")
            idx     = h.get("_index", "")

            parts = [f"[{idx}]"]
            if ts:      parts.append(f"ts={ts}")
            if src_ip:  parts.append(f"src={src_ip}")
            if dst_ip:  parts.append(f"dst={dst_ip}")
            if rule:    parts.append(f"rule={rule}")
            if action:  parts.append(f"action={action}")
            if msg and not src_ip:
                parts.append(f"msg={str(msg)[:120]}")

            lines.append("  " + " | ".join(parts))

    return "\n".join(lines)


def summarize_for_dashboard(
    user_question: str,
    generated_query: dict,
    query_result: dict,
    explanation: str
) -> dict:
    """
    Build the dashboard-ready payload saved to output/latest_query.json.
    Includes everything an analyst needs to verify and reproduce the query.
    """
    total = query_result.get("hits", {}).get("total", {})
    count = total.get("value", 0) if isinstance(total, dict) else total
    hits  = query_result.get("hits", {}).get("hits", [])
    aggs  = query_result.get("aggregations", {})

    return {
        "user_question":     user_question,
        "generated_query":   generated_query,
        "indices_searched":  INDICES,
        "total_hits":        count,
        "explanation":       explanation,
        "aggregations":      aggs,
        "sample_hits":       [h.get("_source", {}) for h in hits[:25]],
        "reproduce_with": {
            "description": "Run this query in OpenSearch Dev Tools to reproduce",
            "method":      "POST",
            "path":        f"/{INDICES}/_search",
            "body":        generated_query
        }
    }


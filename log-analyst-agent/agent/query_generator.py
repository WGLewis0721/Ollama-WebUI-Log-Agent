#!/usr/bin/env python3
"""
query_generator.py — Convert natural language SOC questions to OpenSearch DSL
Uses llama3.2:3b at temperature=0 for deterministic, structured output.
Falls back to a safe match_all query if generation fails.
"""

import json
import re
import requests
import os
from datetime import datetime, timezone, timedelta

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
QUERY_MODEL     = os.getenv("QUERY_MODEL", "llama3.2:3b")
INDICES         = os.getenv("OPENSEARCH_INDEX", "cwl-*,appgate-logs-*,security-logs-*")

# Oldest known log — used as fallback floor for time ranges
LOG_FLOOR = "2026-01-01T00:00:00Z"
LOG_CEIL  = "2026-03-01T00:00:00Z"

SYSTEM_PROMPT = """You are an OpenSearch query generator for a Palo Alto firewall log analysis system on AWS GovCloud IL6.

Your ONLY job is to convert natural language questions into valid OpenSearch DSL JSON.

STRICT OUTPUT RULES:
- Return ONLY raw JSON. No markdown, no backticks, no explanation, no comments.
- Never return anything other than a single valid JSON object.

INDEX: cwl-*,appgate-logs-*,security-logs-*
LOG DATE RANGE: 2026-02-02 to 2026-02-05 (do not use time filters — use match_all for time)

REAL FIELD NAMES (use ONLY these):
  source.ip           - source IP address (keyword)
  source.port         - source port (integer)
  source.zone         - source zone e.g. Trust (keyword)
  destination.ip      - destination IP address (keyword)
  destination.port    - destination port (integer)
  destination.zone    - destination zone e.g. Untrust (keyword)
  rule.name           - firewall rule name (keyword)
  event.action        - allow or deny (keyword)
  network.application - application name (keyword)
  network.bytes       - total bytes (long)
  network.transport   - protocol tcp/udp (keyword)
  network.packets     - packet count (long)
  pa.type             - log type e.g. TRAFFIC (keyword)
  pa.subtype          - log subtype e.g. end (keyword)
  pa.device           - firewall hostname (keyword)
  pa.bytes_sent       - bytes sent (keyword)
  pa.bytes_received   - bytes received (keyword)
  user.name           - username (keyword)
  @timestamp          - event timestamp (date)

KNOWN DATA:
- Only two rules exist: Trust-to-Trust-Allow, Trust-to-Untrust-Allow
- Only action value is: allow (no deny events in dataset)
- Top source IPs: 10.30.4.224, 10.40.2.246, 10.40.2.43
- Top dest IPs: 10.40.2.43, 56.136.225.78, 56.136.224.98

QUERY PATTERNS:
- Top N by frequency: terms aggregation + size:0 + match_all
- List events: size:50, sort @timestamp desc
- Count total: size:0 + match_all
- Filter by IP: term query on source.ip or destination.ip
- Filter by rule: term query on rule.name

EXAMPLES:

User: What are the top 5 source IPs by frequency?
{"size":0,"query":{"match_all":{}},"aggs":{"top_source_ips":{"terms":{"field":"source.ip","size":5,"order":{"_count":"desc"}}}}}

User: Which destination IPs received the most traffic?
{"size":0,"query":{"match_all":{}},"aggs":{"top_dest_ips":{"terms":{"field":"destination.ip","size":5,"order":{"_count":"desc"}}}}}

User: What firewall rules are most active?
{"size":0,"query":{"match_all":{}},"aggs":{"top_rules":{"terms":{"field":"rule.name","size":10,"order":{"_count":"desc"}}}}}

User: Show recent traffic from 10.40.2.246
{"size":50,"sort":[{"@timestamp":{"order":"desc"}}],"query":{"term":{"source.ip":"10.40.2.246"}}}

User: Top destination ports?
{"size":0,"query":{"match_all":{}},"aggs":{"top_ports":{"terms":{"field":"destination.port","size":10,"order":{"_count":"desc"}}}}}

User: How many total log events are there?
{"size":0,"query":{"match_all":{}}}

User: Show traffic going to external IPs
{"size":50,"sort":[{"@timestamp":{"order":"desc"}}],"query":{"term":{"destination.zone":"Untrust"}}}"""


def generate_opensearch_query(user_question: str) -> dict:
    """
    Send user question to llama3.2:3b and parse the returned OpenSearch DSL.
    Returns a valid query dict, or a safe fallback if generation fails.
    """
    try:
        r = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": QUERY_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": f"Convert this to an OpenSearch query: {user_question}"}
                ],
                "stream": False,
                "options": {"temperature": 0}
            },
            timeout=60
        )
        r.raise_for_status()
        raw = r.json().get("message", {}).get("content", "")

        # Strip markdown fences if model added them despite instructions
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()

        # Extract first JSON object from the response
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            raise ValueError(f"No JSON object found in model output: {raw[:200]}")

        query = json.loads(match.group())
        print(f"  [QueryGen] Generated query: {json.dumps(query)[:200]}")
        return query

    except Exception as e:
        print(f"  [QueryGen] WARN: Query generation failed ({e}) — using fallback")
        return _fallback_query(user_question)


def _fallback_query(question: str) -> dict:
    """Safe fallback — return most recent 50 logs across all indices."""
    q = question.lower()

    # Simple keyword routing for common patterns
    if any(w in q for w in ["deny", "denied", "block", "blocked"]):
        return {
            "size": 50,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {"match": {"action": "deny"}},
            "_source": True
        }
    if any(w in q for w in ["top ip", "most frequent ip", "source ip"]):
        return {
            "size": 0,
            "query": {"match_all": {}},
            "aggs": {
                "top_src_ips": {
                    "terms": {"field": "src_ip.keyword", "size": 10}
                }
            }
        }
    if any(w in q for w in ["recent", "latest", "last", "newest"]):
        return {
            "size": 20,
            "sort": [{"@timestamp": {"order": "desc"}}],
            "query": {"match_all": {}}
        }

    # Generic fallback
    return {
        "size": 50,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"match_all": {}}
    }


def is_specific_question(user_query: str) -> bool:
    """
    Determine if the user asked a specific question (→ query mode)
    vs a generic analyze request (→ report mode).
    """
    if not user_query or len(user_query.strip()) < 10:
        return False

    generic_triggers = [
        "analyze", "analyse", "security report", "full report",
        "summarize", "summary", "overview", "what happened",
        "generate report", "run analysis"
    ]
    q = user_query.lower().strip()

    # If it starts with or contains a generic trigger → report mode
    for trigger in generic_triggers:
        if q.startswith(trigger) or f" {trigger}" in q:
            return False

    # If it contains a question word or specific data request → query mode
    question_signals = [
        "which", "what", "who", "how many", "list", "show",
        "top", "most", "least", "count", "when", "where",
        "find", "get", "give me", "tell me"
    ]
    for signal in question_signals:
        if signal in q:
            return True

    # Default: treat longer specific queries as questions
    return len(user_query.strip()) > 30


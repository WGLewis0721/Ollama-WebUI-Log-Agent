# 🤖 CNAP AI Log Analyst

**Ask questions about your network in plain English. Get answers backed by real data.**

---

## The Problem This Solves

Every day the CNAP IL6 environment generates tens of thousands of Palo Alto firewall and AppGate SDP log events. When something looks suspicious — or leadership asks a question — analysts currently have two options:

1. **Manually search OpenSearch Dashboards** — requires knowing DSL query syntax, slow, easy to make mistakes
2. **Wait for a scheduled report** — delayed, generic, not tailored to the specific question being asked

Neither option is fast enough for real operational tempo.

---

## What This Does

This platform lets any analyst ask a natural language question and get an answer backed by a real, auditable OpenSearch query — in seconds.

```
Analyst: "What are the top 5 source IPs hitting the firewall right now?"

Agent:  → Generates OpenSearch DSL query
        → Executes against live cwl-* indices
        → Returns exact counts with plain-language explanation
        → Stores the query in the dashboard for audit
```

No DSL knowledge required. No waiting for reports. Every answer is traceable back to the exact query that produced it.

---

## Why This Matters for Zero Trust

This platform is a **force multiplier for the AppGate SDP zero-trust architecture** already running in the IL6 environment.

Zero trust means every connection is logged, validated, and auditable. But that value is only realized if someone can actually interrogate those logs quickly. This system closes that gap:

| Zero Trust Principle | How This Helps |
|---|---|
| **Verify explicitly** | Instantly query "show me all sessions from this identity" — no DSL required |
| **Assume breach** | Rapid detection — ask "what IPs generated anomalous traffic?" and get answers in seconds |
| **Least privilege audit** | Cross-reference AppGate session logs against firewall rules conversationally |
| **Audit trail** | Every AI-generated query is stored in the dashboard — answers are reproducible and verifiable |

When leadership or an auditor asks "how do you know that?" — the answer is a stored DSL query that anyone can re-run.

---

## How It Works

The system has two modes that activate automatically based on what you ask:

**Query Mode** — for specific factual questions:
```
"Which source IP had the most connections yesterday?"
"Show me all traffic from the Untrust zone"
"Which firewall rule has the highest hit count?"
```
The agent generates a precise OpenSearch DSL query, executes it, and explains the real results.

**Report Mode** — for broad analysis requests:
```
"Give me a SOC summary of today's activity"
"Analyze the last 24 hours of firewall logs"
"Are there any security concerns in the recent traffic?"
```
The agent fetches a representative log sample, applies runbook context from the knowledge base, and generates a structured SOC narrative.

---

## Architecture at a Glance

```
Analyst
  ↓
OpenWebUI  (:8080)          — ChatGPT-style chat interface
  ↓
FastAPI Agent  (:7000)      — Routing and orchestration
  ├── Query mode  →  llama3.2:3b generates DSL  →  OpenSearch executes  →  llama3.1:8b explains
  └── Report mode  →  RAG retrieves runbook context  →  llama3.1:8b writes SOC report
  ↓
Dashboard  (:5000)          — Query audit trail and report history
  ↓
Ollama  (:11434)            — Local GPU inference on Tesla T4 (no data leaves the enclave)
OpenSearch  (VPC endpoint)  — Live cwl-*, appgate-logs-*, security-logs-* indices
```

**All inference runs locally.** Ollama runs on a Tesla T4 GPU inside the IL6 VPC. No data is sent to any external API.

---

## What You Can Ask

**Firewall traffic:**
- `What are the top 10 source IPs by connection count?`
- `Show me all traffic destined for port 443`
- `Which firewall rule has the most hits?`
- `Are there any IPs talking to unusual external destinations?`

**AppGate / Zero Trust:**
- `Summarize AppGate session activity from this morning`
- `Show sessions from the Trust zone to Untrust zone`

**SOC summaries:**
- `Give me an analyst briefing on today's traffic`
- `Are there any patterns I should be aware of?`
- `Summarize unusual outbound connections`

---

## Services

| Container | Port | Role |
|---|---|---|
| `open-webui` | 8080 | Primary analyst chat interface |
| `log-analyst-rag` | 7000 | FastAPI agent — query generation, RAG, OpenSearch |
| `log-analyst-dashboard` | 5000 | Report history and query audit trail |
| `ollama` | 11434 | Local LLM inference (Tesla T4 GPU) |

---

## Models

| Model | Role |
|---|---|
| `llama3.2:3b` | OpenSearch DSL generation — deterministic (temp=0) |
| `llama3.1:8b` | SOC reports and result explanation |
| `nomic-embed-text` | RAG vector embeddings for runbook retrieval |

---

## Log Sources

| Index | Source | Contents |
|---|---|---|
| `cwl-*` | Palo Alto NGFW via CloudWatch → FluentBit | Firewall traffic logs |
| `appgate-logs-*` | AppGate SDP via rsyslog | Zero-trust session events |
| `security-logs-*` | Security tooling | Additional telemetry |
| `knowledge-base` | S3 runbooks → indexed locally | SOC procedures and playbooks |

---

## Infrastructure

| Parameter | Value |
|---|---|
| Instance | `g4dn.xlarge` — Tesla T4, 15360 MiB VRAM |
| OS | Ubuntu 22.04 LTS |
| Region | `us-gov-west-1` (AWS GovCloud West) |
| IAM Role | `LogAnalystEC2Role` |
| ECR Image | `235856440647.dkr.ecr.us-gov-west-1.amazonaws.com/cnap-log-analyst-rag:v3` |
| AMI (v3 snapshot) | `ami-0a6d2fcf26f229fe1` |
| Access | Private subnet — via bastion `10.110.6.37` |

---

## Quick Start

If deploying from the v3 AMI or ECR image, the environment is pre-configured. Start the stack:

```bash
cd ~/log-analyst-agent
sudo docker compose -f docker-compose-rag.yml up -d
sudo docker compose -f docker-compose-rag.yml ps
```

Access via SSH tunnel from your local machine:

```bash
ssh -i ~/.ssh/IL6-Zero-Trust-Key.pem \
  -L 8080:10.40.0.90:8080 \
  -L 5000:10.40.0.90:5000 \
  -L 7000:10.40.0.90:7000 \
  ec2-user@<bastion-public-ip> -N
```

| Interface | URL | What it does |
|---|---|---|
| OpenWebUI | http://localhost:8080 | Start chatting with the analyst |
| Dashboard | http://localhost:5000 | Browse reports and query audit trail |
| API (Swagger) | http://localhost:7000/docs | Raw API and health check |

For a fresh install, see **[SETUP.md](./SETUP.md)**.

---

## Everyday Commands

```bash
# Start
cd ~/log-analyst-agent
sudo docker compose -f docker-compose-rag.yml up -d

# Stop
sudo docker compose -f docker-compose-rag.yml down

# Check status
sudo docker compose -f docker-compose-rag.yml ps

# Live logs from the agent
sudo docker logs -f log-analyst-rag

# Check GPU utilization
nvidia-smi

# Read the latest analysis report
cat $(ls -t ~/log-analyst-agent/output/analysis_rag_*.txt | head -1)
```

---

## Repository Structure

```
log-analyst-agent/
├── docker-compose-rag.yml          ← Start here — runs the full stack
├── .env.example                    ← Copy to agent/.env.rag and fill in values
├── .env.opensearch.example
├── SETUP.md                        ← Full from-scratch setup guide
├── README.md                       ← This file
├── Makefile
├── agent/
│   ├── Dockerfile
│   ├── api_server.py               ← FastAPI dual-mode router
│   ├── main_rag.py                 ← RAG pipeline + /api/chat
│   ├── query_generator.py          ← llama3.2:3b → OpenSearch DSL
│   ├── opensearch_executor.py      ← Executes DSL, formats results
│   ├── opensearch_integration.py   ← AWS4Auth OpenSearch client
│   ├── rag_module.py               ← kNN embeddings (nomic-embed-text)
│   ├── dashboard.py                ← Flask report history UI
│   ├── document_indexer.py         ← S3 runbooks → knowledge-base index
│   ├── requirements.txt
│   └── templates/
│       └── dashboard.html
├── knowledge-base/
│   └── runbooks/                   ← Drop .md runbooks here, then re-index
├── config/
└── misc/                           ← Dev artifacts — not needed for deployment
```

---

## Known Limitations

| Issue | Status |
|---|---|
| `appgate-logs-*` DSL queries return 0 results | Under investigation — field mapping differs from `cwl-*` |
| Log dataset is from Feb 2026 | `match_all` used — no time filter — queries still return results |
| Knowledge base is thin (~10 chunks) | Re-index with CNAP-specific runbooks from S3 |

---

## Security Notes

Do not commit real `.env` or `.env.rag` files, AWS credentials, session tokens, internal hostnames, VPC endpoint URLs, or raw output files from `/output`. Commit only sanitized templates: `.env.example`, `.env.opensearch.example`.

---

## Roadmap

- [ ] AppGate field mapping investigation and DSL support
- [ ] Time-aware prompting (eliminate year hallucination)
- [ ] Intent classifier to replace keyword-based mode routing
- [ ] Stronger DSL query guardrails (cap size, validate sort fields)
- [ ] Expanded CNAP runbook coverage in knowledge base
- [ ] Multi-step investigation workflows

---

Built by the CNAP Engineering team — Cloud One Operations, SAIC / Gunter AFB

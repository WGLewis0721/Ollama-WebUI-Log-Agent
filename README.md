# Ollama-WebUI-Log-Agent 🤖

An AI-powered, production-ready log analysis and SOC (Security Operations Center) assistant built on **Ollama**, **OpenSearch**, **RAG (Retrieval-Augmented Generation)**, and **Open WebUI**. Designed for DoD IL6 / AWS GovCloud environments and engineered for cost-effective, self-hosted LLM inference.

---

## 🗂️ Repository Structure

```
Ollama-WebUI-Log-Agent/
├── README.md                          ← You are here
├── SETUP_GUIDE.md                     ← Step-by-step installation & configuration
├── IMPROVEMENTS.md                    ← Optimization & enhancement suggestions
├── log-analyst-agent-v3-*.zip         ← Source archive (v3 release)
└── log-analyst-agent/                 ← Main project directory
    ├── agent/                         ← Core Python agent application
    │   ├── api_server.py              ← FastAPI server (OpenAI-compatible, port 7000)
    │   ├── main_rag.py                ← RAG pipeline bridge (OpenSearch + LLM)
    │   ├── main_opensearch.py         ← OpenSearch-only analysis mode
    │   ├── main.py                    ← Local file-based analysis (basic mode)
    │   ├── query_generator.py         ← NL-to-OpenSearch DSL converter (llama3.2:3b)
    │   ├── opensearch_executor.py     ← Query execution and result formatter
    │   ├── opensearch_integration.py  ← AWS OpenSearch client (SigV4 auth)
    │   ├── rag_module.py              ← RAG retrieval (vector search via nomic-embed-text)
    │   ├── rag_indexer.py             ← Index documents into OpenSearch knowledge-base
    │   ├── s3_document_fetcher.py     ← Fetch runbooks/docs from S3
    │   ├── document_indexer.py        ← Document chunking and embedding pipeline
    │   ├── dashboard.py               ← Flask dashboard server (port 5000)
    │   ├── templates/dashboard.html   ← Real-time SOC dashboard UI
    │   ├── Dockerfile                 ← Agent container image
    │   └── requirements.txt           ← Python dependencies
    ├── docker-compose-rag.yml         ← Full RAG stack (Ollama + Agent + Dashboard + Open WebUI)
    ├── docker-compose-opensearch.yml  ← OpenSearch-only stack
    ├── docker-compose.yml             ← Basic local analysis stack
    ├── Dockerfile.open-webui          ← Custom Open WebUI image
    ├── Makefile                       ← Convenience make targets
    ├── start.sh                       ← Bootstrap script
    ├── setup-rag.sh                   ← RAG environment setup
    ├── setup-opensearch.sh            ← OpenSearch index configuration
    ├── deploy_main_rag.sh             ← Deploy v3 agent to running container
    ├── deploy-ec2.sh                  ← EC2 provisioning script
    ├── test.sh                        ← Integration test suite
    ├── log-analyst.service            ← systemd service definition
    ├── log-analyst-policy-v2.json     ← IAM policy for EC2 role
    ├── knowledge-base/                ← RAG document store
    │   ├── runbooks/                  ← Operational runbooks
    │   ├── incidents/                 ← Past incident reports
    │   ├── standards/                 ← Security standards
    │   └── documentation/             ← General documentation
    ├── logs/                          ← Input: log files for analysis
    ├── config/                        ← Optional: custom configurations
    ├── .env.example                   ← Basic config template
    ├── .env.opensearch.example        ← OpenSearch config template
    ├── .env.rag                       ← RAG stack config (update before use)
    └── docs/
        ├── README.md                  ← Original project README
        ├── ARCHITECTURE.md            ← System architecture deep-dive
        ├── COMPLETE_SOLUTION.md       ← Full solution overview & cost breakdown
        ├── OPENSEARCH_INTEGRATION.md  ← OpenSearch setup guide
        ├── OPENSEARCH_COMPLETE_GUIDE.md
        ├── RAG_COST_EFFECTIVE_GUIDE.md
        ├── OPTION3_DEPLOYMENT_GUIDE.md
        ├── OPTION3_QUICK_CHECKLIST.md
        ├── QUICKREF.md                ← Quick reference card
        └── database-troubleshooting.md
```

---

## 🏗️ System Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                     Your Applications                          │
│          (Kubernetes, Docker, EC2, Lambda, etc.)               │
└──────────────────────┬────────────────────────────────────────┘
                       │ stdout / stderr
                       ▼
              ┌─────────────────┐
              │   Fluent Bit    │  (pre-existing)
              └────────┬────────┘
                       │ Forward logs
                       ▼
         ┌─────────────────────────────┐
         │   AWS OpenSearch Cluster    │
         │  cwl-*  |  knowledge-base   │
         └──────┬──────────────────────┘
                │                │
        Fetch logs         Fetch RAG context
                │                │
                ▼                ▼
┌──────────────────────────────────────────────────────┐
│                    EC2 Instance                       │
│                                                       │
│  ┌──────────┐   ┌────────────────┐   ┌───────────┐  │
│  │  Ollama  │◄──│  Log Analyst   │◄──│    RAG    │  │
│  │  :11434  │   │  Agent :7000   │   │  Module   │  │
│  └──────────┘   └───────┬────────┘   └───────────┘  │
│                          │                            │
│                  ┌───────▼────────┐                  │
│                  │  Dashboard     │                  │
│                  │  (Flask :5000) │                  │
│                  └────────────────┘                  │
└──────────────────────────┬───────────────────────────┘
                            │ HTTP
                            ▼
                  ┌──────────────────┐
                  │  Open WebUI      │
                  │  :8080           │
                  │ (Chat interface) │
                  └──────────────────┘
```

---

## 🚀 Deployment Modes

| Mode | Compose File | Use Case |
|------|-------------|----------|
| **Basic** | `docker-compose.yml` | Analyze local `.log` files |
| **OpenSearch** | `docker-compose-opensearch.yml` | Query live OpenSearch indices |
| **RAG (v3)** | `docker-compose-rag.yml` | Full stack: OpenSearch + RAG + Open WebUI |

---

## 💰 Cost Summary

| Component | Monthly Cost |
|-----------|-------------|
| EC2 t3.xlarge | ~$120 |
| OpenSearch | $0 (existing) |
| S3 Knowledge Base | ~$2–10 |
| Ollama / LLMs | $0 (self-hosted) |
| **Total** | **~$122–130** |

> Compared to $700+/month for commercial alternatives (Pinecone, OpenAI API, etc.)

---

## 📚 Key Documents

| Document | Purpose |
|----------|---------|
| [SETUP_GUIDE.md](./SETUP_GUIDE.md) | Step-by-step installation and configuration guide |
| [IMPROVEMENTS.md](./IMPROVEMENTS.md) | Optimization, security, and feature suggestions |
| [log-analyst-agent/ARCHITECTURE.md](./log-analyst-agent/ARCHITECTURE.md) | Detailed system architecture |
| [log-analyst-agent/COMPLETE_SOLUTION.md](./log-analyst-agent/COMPLETE_SOLUTION.md) | Full solution overview with cost breakdown |
| [log-analyst-agent/QUICKREF.md](./log-analyst-agent/QUICKREF.md) | Quick reference for daily operations |
| [log-analyst-agent/RAG_COST_EFFECTIVE_GUIDE.md](./log-analyst-agent/RAG_COST_EFFECTIVE_GUIDE.md) | RAG implementation cost guide |
| [log-analyst-agent/OPENSEARCH_COMPLETE_GUIDE.md](./log-analyst-agent/OPENSEARCH_COMPLETE_GUIDE.md) | OpenSearch integration guide |

---

## ⚡ Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/WGLewis0721/Ollama-WebUI-Log-Agent.git
cd Ollama-WebUI-Log-Agent

# 2. Configure environment
cp log-analyst-agent/.env.example log-analyst-agent/.env
# Edit .env with your OpenSearch endpoint and AWS credentials

# 3. Start the full RAG stack
cd log-analyst-agent
docker compose -f docker-compose-rag.yml up -d

# 4. Open the chat UI
open http://localhost:8080
```

> See [SETUP_GUIDE.md](./SETUP_GUIDE.md) for full installation instructions.

---

## 🔧 LLM Models

| Model | RAM | Speed | Best For |
|-------|-----|-------|----------|
| `llama3.2:3b` | 4 GB | Fast | Query generation, quick scans |
| `llama3.1:8b` | 8 GB | Medium | Full SOC reports, analysis |
| `llama3:70b` | 48 GB+ | Slow | Maximum accuracy |
| `nomic-embed-text` | 1 GB | Fast | Embeddings (always required) |

---

## 🛡️ Security & Compliance

- Designed for **DoD IL6 / AWS GovCloud** (`us-gov-west-1`)
- All inference runs **locally** — no data leaves your environment
- IAM policy template included: `log-analyst-policy-v2.json`
- SigV4 request signing for all OpenSearch API calls
- Read-only log mounts in all containers

---

Built with ❤️ using Ollama, FastAPI, OpenSearch, and Open WebUI

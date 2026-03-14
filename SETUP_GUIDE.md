# Setup Guide — Log Analyst Agent v3

This guide walks you through a full installation of the **CNAP Log Analyst Agent v3**, from a bare EC2 instance to a running Open WebUI chat interface backed by OpenSearch and RAG.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Infrastructure Overview](#2-infrastructure-overview)
3. [EC2 Instance Setup](#3-ec2-instance-setup)
4. [Clone the Repository](#4-clone-the-repository)
5. [Configure Environment Variables](#5-configure-environment-variables)
6. [Configure AWS Credentials (IAM Role)](#6-configure-aws-credentials-iam-role)
7. [Build & Start the Full RAG Stack](#7-build--start-the-full-rag-stack)
8. [Pull Required Ollama Models](#8-pull-required-ollama-models)
9. [Index the Knowledge Base](#9-index-the-knowledge-base)
10. [Verify All Services](#10-verify-all-services)
11. [Access the Web Interface](#11-access-the-web-interface)
12. [Running as a systemd Service](#12-running-as-a-systemd-service)
13. [Basic Mode (Local Log Files)](#13-basic-mode-local-log-files)
14. [OpenSearch-Only Mode](#14-opensearch-only-mode)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. Prerequisites

### Software Requirements

| Tool | Version | Purpose |
|------|---------|---------|
| Docker | 24.x+ | Container runtime |
| Docker Compose | v2.x+ | Multi-container orchestration |
| Git | 2.x+ | Repository cloning |
| AWS CLI | v2.x | Credential validation |

### Hardware Requirements

| Tier | Instance | RAM | vCPU | Use Case |
|------|----------|-----|------|----------|
| Minimum | t3.large | 8 GB | 2 | Dev / testing with 3B model |
| Recommended | t3.xlarge | 16 GB | 4 | Production with 8B model |
| Optimal | g4dn.xlarge | 16 GB + GPU | 4 | GPU-accelerated inference |

### AWS Requirements

- AWS account with access to the target region (`us-gov-west-1` or equivalent)
- An existing **AWS OpenSearch** cluster with indices matching:
  - `cwl-*` (CloudWatch Logs via Fluent Bit)
  - `appgate-logs-*` (AppGate logs)
  - `security-logs-*` (security events)
- An **S3 bucket** containing knowledge-base documents (runbooks, SOPs, incident reports)
- An **EC2 IAM Role** attached to the instance (see [Section 6](#6-configure-aws-credentials-iam-role))

---

## 2. Infrastructure Overview

```
Internet / VPN
     │
     ▼
EC2 Instance (Ubuntu 22.04 LTS)
  ├── Port 8080  → Open WebUI (chat interface)
  ├── Port 5000  → SOC Dashboard (Flask)
  ├── Port 7000  → Log Analyst API (FastAPI, internal)
  └── Port 11434 → Ollama (LLM inference, internal only)
```

> **Security Note**: Ports 7000 and 11434 should be restricted to the EC2 Security Group only (no public access). Only ports 8080 and 5000 need to be reachable by end users.

---

## 3. EC2 Instance Setup

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ubuntu@<your-ec2-public-ip>

# Update the system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
newgrp docker   # Reload group without logout

# Verify Docker
docker --version
docker compose version

# (GPU instances only) Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release; echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

---

## 4. Clone the Repository

```bash
git clone https://github.com/WGLewis0721/Ollama-WebUI-Log-Agent.git
cd Ollama-WebUI-Log-Agent/log-analyst-agent
```

---

## 5. Configure Environment Variables

### Copy the template

```bash
cp .env.example .env.rag
```

### Edit `.env.rag` with your values

```bash
nano .env.rag
```

```dotenv
# ── OpenSearch ──────────────────────────────────────────────────────────────
OPENSEARCH_ENDPOINT=<your-opensearch-domain>.us-gov-west-1.es.amazonaws.com
OPENSEARCH_INDEX=cwl-*,appgate-logs-*,security-logs-*
AWS_REGION=us-gov-west-1

# ── Ollama (LLM) ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=llama3.1:8b          # Main analysis model
QUERY_MODEL=llama3.2:3b         # Query generation model (faster)

# ── RAG Configuration ────────────────────────────────────────────────────────
ENABLE_RAG=true
RAG_K=3                         # Number of RAG documents to retrieve
RAG_INDEX=knowledge-base        # OpenSearch index for RAG documents
S3_KNOWLEDGE_BASE_BUCKET=<your-s3-bucket-name>

# ── Analysis Settings ────────────────────────────────────────────────────────
TIME_RANGE_MINUTES=64800        # How far back to fetch logs (~45 days)
WATCH_MODE=true                 # Enable continuous background analysis
WATCH_INTERVAL_MINUTES=30       # Re-analyze every N minutes

# ── Output ───────────────────────────────────────────────────────────────────
OUTPUT_DIR=/app/output
```

> ⚠️ **Never commit `.env.rag` with real credentials**. It is listed in `.gitignore`.

---

## 6. Configure AWS Credentials (IAM Role)

The agent uses the **EC2 instance's IAM role** for authentication. No static credentials are needed.

### Create and attach an IAM Role

1. Go to **IAM → Roles → Create Role**
2. Select **EC2** as the trusted entity
3. Attach a custom inline policy using `log-analyst-policy-v2.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["es:ESHttpGet", "es:ESHttpPost", "es:ESHttpPut"],
      "Resource": "arn:aws-us-gov:es:us-gov-west-1:<account-id>:domain/<domain-name>/*"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:ListBucket"],
      "Resource": [
        "arn:aws-us-gov:s3:::<your-knowledge-base-bucket>",
        "arn:aws-us-gov:s3:::<your-knowledge-base-bucket>/*"
      ]
    }
  ]
}
```

4. Attach the role to your EC2 instance: **EC2 → Instance → Actions → Security → Modify IAM Role**

### Verify credentials are available

```bash
# From the EC2 instance (no AWS CLI config needed with an instance role)
curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/
# Should return your role name
```

---

## 7. Build & Start the Full RAG Stack

```bash
cd /path/to/Ollama-WebUI-Log-Agent/log-analyst-agent

# Build and start all services (Ollama + Agent + Dashboard + Open WebUI)
docker compose -f docker-compose-rag.yml up -d --build

# Follow startup logs
docker compose -f docker-compose-rag.yml logs -f
```

Expected service startup order:
1. `ollama` — starts and becomes healthy (model list responds)
2. `log-analyst-rag` — FastAPI server starts on port 7000
3. `dashboard` — Flask server starts on port 5000
4. `open-webui` — Web UI starts on port 8080

### Check service status

```bash
docker compose -f docker-compose-rag.yml ps
```

All services should show **Up** or **Up (healthy)**.

---

## 8. Pull Required Ollama Models

```bash
# Pull the main analysis model
docker exec ollama ollama pull llama3.1:8b

# Pull the query generation model
docker exec ollama ollama pull llama3.2:3b

# Pull the embedding model (required for RAG)
docker exec ollama ollama pull nomic-embed-text

# Verify models are available
docker exec ollama ollama list
```

Expected output:
```
NAME                    ID            SIZE   MODIFIED
llama3.1:8b             ...           4.7 GB  ...
llama3.2:3b             ...           2.0 GB  ...
nomic-embed-text:latest ...           274 MB  ...
```

> First pulls may take 5–20 minutes depending on network speed.

---

## 9. Index the Knowledge Base

The knowledge base powers RAG context for the agent. It reads documents from your S3 bucket and creates vector embeddings in OpenSearch.

```bash
# Run the RAG indexer (one-time setup, re-run when docs change)
docker exec log-analyst-rag python rag_indexer.py

# Alternatively, to fetch from S3 and index:
docker exec log-analyst-rag python document_indexer.py
```

### Adding documents to the knowledge base

Place your documents in the S3 bucket configured by `S3_KNOWLEDGE_BASE_BUCKET`:

```
s3://<bucket>/
├── runbooks/
│   ├── incident-response.md
│   └── escalation-procedures.md
├── standards/
│   └── security-baseline.md
└── documentation/
    └── network-topology.md
```

You can also add documents locally to `knowledge-base/` and they will be picked up by the indexer.

---

## 10. Verify All Services

```bash
# Check Ollama API
curl http://localhost:11434/api/tags

# Check the Log Analyst API health
curl http://localhost:7000/health
# Expected: {"status": "ok"}

# Check available models via the OpenAI-compatible endpoint
curl http://localhost:7000/v1/models
# Expected: {"data": [{"id": "log-analyst-rag", ...}]}

# Check Dashboard
curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/
# Expected: 200

# Check Open WebUI
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/
# Expected: 200
```

---

## 11. Access the Web Interface

Open a browser and navigate to:

| Interface | URL | Purpose |
|-----------|-----|---------|
| **Open WebUI** | `http://<ec2-ip>:8080` | Main chat interface |
| **SOC Dashboard** | `http://<ec2-ip>:5000` | Real-time analysis dashboard |
| **API Docs** | `http://<ec2-ip>:7000/docs` | FastAPI auto-docs |

### First-time Open WebUI setup

1. Navigate to `http://<ec2-ip>:8080`
2. Create an admin account (first user becomes admin)
3. Select the model **`log-analyst-rag`** from the model picker
4. Start chatting — example queries:
   - "Show me the top source IPs from the last 24 hours"
   - "Were there any denied connections to port 443?"
   - "Summarize security events from this week"
   - "Generate a SOC report for today"

---

## 12. Running as a systemd Service

To ensure the stack starts automatically on boot:

```bash
sudo cp log-analyst-agent/log-analyst.service /etc/systemd/system/log-analyst.service

# Edit the service file to point to your project directory
sudo nano /etc/systemd/system/log-analyst.service

sudo systemctl daemon-reload
sudo systemctl enable log-analyst
sudo systemctl start log-analyst
sudo systemctl status log-analyst
```

---

## 13. Basic Mode (Local Log Files)

If you don't have OpenSearch, you can analyze local `.log` files:

```bash
cd log-analyst-agent

# Place log files in the logs/ directory
cp /path/to/your/app.log logs/

# Start basic analysis
docker compose -f docker-compose.yml up

# Results saved to output/
ls output/
```

### Configuration for basic mode

Edit `docker-compose.yml`:

```yaml
environment:
  - MODEL_NAME=llama3.2:3b      # Model to use
  - ANALYSIS_TYPE=security       # general | security | performance | errors
  - WATCH_MODE=false             # true for continuous monitoring
```

---

## 14. OpenSearch-Only Mode

For OpenSearch integration without RAG:

```bash
cp .env.opensearch.example .env.opensearch
# Edit with your OpenSearch credentials

docker compose -f docker-compose-opensearch.yml up -d
```

---

## 15. Troubleshooting

### Ollama takes too long to start

```bash
# Watch Ollama health check
docker logs ollama -f

# Manually test the Ollama API
docker exec ollama curl http://localhost:11434/api/tags
```

### Agent can't connect to OpenSearch

```bash
# Test from inside the container
docker exec log-analyst-rag python -c "
import os, requests
endpoint = os.environ['OPENSEARCH_ENDPOINT']
print(requests.get(f'https://{endpoint}/_cluster/health').json())
"
```

Common causes:
- EC2 Security Group does not allow outbound to OpenSearch's VPC endpoint
- IAM role lacks `es:ESHttpGet` permission
- Wrong `OPENSEARCH_ENDPOINT` value (do not include `https://`)

### Out of memory / OOM killed

```bash
# Check available memory
free -h

# Switch to a smaller model in .env.rag
MODEL_NAME=llama3.2:3b
```

### Open WebUI shows "No models available"

```bash
# Verify the agent API is healthy
curl http://localhost:7000/v1/models

# Restart Open WebUI
docker compose -f docker-compose-rag.yml restart open-webui
```

### RAG returns no context

```bash
# Re-run the indexer
docker exec log-analyst-rag python rag_indexer.py

# Check the knowledge-base index in OpenSearch
curl https://<opensearch-endpoint>/knowledge-base/_count
```

### View all logs at once

```bash
docker compose -f docker-compose-rag.yml logs --tail=50
```

---

## Makefile Reference

```bash
make build        # Build Docker images
make up           # Start services (basic stack)
make down         # Stop services
make logs         # Tail agent logs
make status       # Show container status
make pull-model   # Pull/update the LLM model
make restart      # Restart all services
make clean        # Remove containers and volumes
make test         # Run analysis on example logs
```

---

*For architecture details, see [log-analyst-agent/ARCHITECTURE.md](./log-analyst-agent/ARCHITECTURE.md).*
*For cost and RAG implementation details, see [log-analyst-agent/RAG_COST_EFFECTIVE_GUIDE.md](./log-analyst-agent/RAG_COST_EFFECTIVE_GUIDE.md).*

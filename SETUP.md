# 🍳 Setup Guide

> **What you're building:** An AI-powered SOC log analysis platform on a GPU instance in AWS GovCloud IL6.
> By the end you'll have 4 Docker containers running, Ollama serving local LLMs on a Tesla T4, and analysts
> querying Palo Alto firewall logs in plain English.

**Choose your path before you start:**

| Path | When to use | Time |
|---|---|---|
| **[Path A — From ECR Image](#-path-a--deploy-from-ecr-image-recommended)** | New instance, image already built and pushed | ~15 min |
| **[Path B — From ZIP Archive](#-path-b--deploy-from-zip-archive)** | Air-gapped restore, no ECR access | ~20 min |
| **[Path C — From Scratch](#-path-c--build-from-scratch)** | Brand new instance with nothing installed | ~45 min |

All three paths converge at **[Final Steps](#-final-steps--configure-and-start)**.

---

## 🧾 What You'll Need (All Paths)

Before you start, confirm you have everything:

- [ ] Access to the bastion host (`i-0fc82dadfd4532970`)
- [ ] `IL6-Zero-Trust-Key.pem` on your local machine
- [ ] A `g4dn.xlarge` EC2 instance running **Ubuntu 22.04** in `vpc-0b571ce44509fdf19`
- [ ] IAM role `LogAnalystEC2Role` attached to the instance
- [ ] The OpenSearch VPC endpoint URL (get from your team lead or AWS console)
- [ ] GitLab access (Path C only)

---

## 🔗 How to Connect

The log analyst host has no public IP. You must always go through the bastion.

**On your local machine — connect to the bastion:**
```bash
ssh -i ~/.ssh/IL6-Zero-Trust-Key.pem ec2-user@<bastion-public-ip>
```

**On the bastion — hop to the log analyst host:**
```bash
ssh -i IL6-Zero-Trust-Key.pem ubuntu@10.40.0.90
```

> 💡 Open two terminal tabs before you start — one on the bastion for AWS CLI commands,
> one on the log analyst host for everything else.

---

## 🐳 Path A — Deploy from ECR Image (Recommended)

Use this when you have a fresh Ubuntu instance and want to pull the pre-built image from ECR.

### A1 — Install Docker

```bash
# Add Docker's repo and GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli docker-compose-plugin

# Let the ubuntu user run Docker without sudo
sudo usermod -aG docker ubuntu
newgrp docker
```

✅ **Done when:** `docker --version` returns without error.

---

### A2 — Pull the Image from ECR

```bash
AWS_ACCOUNT=235856440647
AWS_REGION=us-gov-west-1
ECR_REPO=cnap-log-analyst-rag

# Log in to ECR
aws ecr get-login-password --region $AWS_REGION | \
  sudo docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Pull the v3 image
sudo docker pull \
  ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:v3

# Tag it so docker-compose can find it by the expected name
sudo docker tag \
  ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:v3 \
  log-analyst-agent-log-analyst-rag:latest
```

✅ **Done when:** `sudo docker images` shows `log-analyst-agent-log-analyst-rag`.

---

### A3 — Get the Compose File and Config

```bash
cd ~
git clone https://gitlab.cce.af.mil/cloudone-operations-and-support/c1-ops-and-sustainment/cnap/engineering/il6-pioneers/ollama-openwebui-agent-wgl.git
cd ollama-openwebui-agent-wgl/log-analyst-agent
```

➡️ **Continue to [Final Steps](#-final-steps--configure-and-start)**

---

## 📦 Path B — Deploy from ZIP Archive

Use this when ECR is unreachable or you're restoring from a saved deployment archive.

### B1 — Install Docker (same as A1)

```bash
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli docker-compose-plugin

sudo usermod -aG docker ubuntu
newgrp docker
```

---

### B2 — Download and Extract the ZIP from S3

```bash
cd ~
aws s3 cp \
  s3://cnap-dev-il6-ollama-knowledge-base-wgl/deployments/log-analyst-agent-v3-20260313-003705.zip \
  ./log-analyst-agent-v3.zip \
  --region us-gov-west-1

unzip log-analyst-agent-v3.zip
cd log-analyst-agent
```

---

### B3 — Load the Docker Image

```bash
# Load the pre-exported image from the archive
sudo docker load < log-analyst-agent-log-analyst-rag.tar.gz
```

> ⚠️ If the tar is not included in the ZIP, pull it from S3 directly:
> ```bash
> aws s3 cp \
>   s3://cnap-dev-il6-ollama-knowledge-base-wgl/ecr-transfer/log-analyst-rag-v3.tar.gz \
>   - | gunzip | sudo docker load
> ```

✅ **Done when:** `sudo docker images` shows `log-analyst-agent-log-analyst-rag`.

➡️ **Continue to [Final Steps](#-final-steps--configure-and-start)**

---

## 🔧 Path C — Build from Scratch

Use this only on a completely bare Ubuntu 22.04 instance. The v3 AMI (`ami-0a6d2fcf26f229fe1`)
already has Steps C1–C4 complete — if using it, jump straight to [C5](#c5--clone-the-repository).

---

### C1 — Update the System

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y git unzip curl python3-pip awscli
```

✅ **Done when:** No errors, prompt returns.

---

### C2 — Install the NVIDIA GPU Driver

> ⚠️ Do not skip this step. Without it Ollama can't see the GPU and inference will be painfully slow.

```bash
sudo add-apt-repository ppa:graphics-drivers/ppa -y
sudo apt-get update
sudo apt-get install -y nvidia-driver-590-open nvidia-utils-590
sudo apt-get install -y nvidia-container-toolkit nvidia-container-toolkit-base
```

**Verify it worked:**
```bash
nvidia-smi
```

✅ **Done when:** Output shows the Tesla T4 with `15360 MiB` of memory and `Driver Version: 590.48.01`.

> ⚠️ If `nvidia-smi` fails with an error, reboot and try again:
> ```bash
> sudo reboot
> # then reconnect and re-run nvidia-smi
> ```

---

### C3 — Install Docker

```bash
# Add Docker repo
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli docker-compose-plugin docker-buildx-plugin

# Allow ubuntu user to run Docker without sudo
sudo usermod -aG docker ubuntu
newgrp docker

# Wire Docker into the NVIDIA runtime so containers can see the GPU
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

**Verify:**
```bash
docker --version
# Expected: Docker version 29.x

docker run --rm --gpus all nvidia/cuda:11.0.3-base-ubuntu20.04 nvidia-smi
# Expected: Tesla T4 output
```

✅ **Done when:** Both commands succeed and the GPU test shows the Tesla T4.

---

### C4 — Install Python Dependencies

```bash
pip3 install boto3 opensearch-py requests-aws4auth
pip3 install fastapi uvicorn flask langchain
```

✅ **Done when:** No errors. Add `--user` if you see permission errors.

---

### C5 — Clone the Repository

```bash
cd ~
git clone https://gitlab.cce.af.mil/cloudone-operations-and-support/c1-ops-and-sustainment/cnap/engineering/il6-pioneers/ollama-openwebui-agent-wgl.git
cd ollama-openwebui-agent-wgl/log-analyst-agent
```

✅ **Done when:** `ls` shows `docker-compose-rag.yml` and the `agent/` directory.

---

### C6 — Build the Docker Image from Source

```bash
sudo docker compose -f docker-compose-rag.yml build
```

> ⏱️ First build takes 3–5 minutes — it downloads base images and installs Python requirements.

✅ **Done when:** Build finishes with no errors.

➡️ **Continue to [Final Steps](#-final-steps--configure-and-start)**

---

## ✅ Final Steps — Configure and Start

Everyone arrives here. Three steps to go.

---

### Step 1 — Configure the Environment File

```bash
# Make sure you're in the project root
pwd
# Should show: .../log-analyst-agent

cp .env.opensearch.example agent/.env.rag
nano agent/.env.rag
```

Fill in the file — lines marked `← REQUIRED` must be updated:

```env
# ← REQUIRED: get from your team lead or AWS console — no https://, no trailing slash
OPENSEARCH_ENDPOINT=<vpc-endpoint>.us-gov-west-1.es.amazonaws.com

# Leave these as-is
OPENSEARCH_INDEX=cwl-*,appgate-logs-*,security-logs-*
AWS_REGION=us-gov-west-1
OLLAMA_BASE_URL=http://ollama:11434
MODEL_NAME=llama3.1:8b
QUERY_MODEL=llama3.2:3b
ENABLE_RAG=true
RAG_K=3
RAG_INDEX=knowledge-base

# ← REQUIRED: your S3 knowledge base bucket
S3_KNOWLEDGE_BASE_BUCKET=cnap-dev-il6-ollama-knowledge-base-wgl

# Set high so historical logs are not filtered out by time
TIME_RANGE_MINUTES=99999

# Leave as-is
OUTPUT_DIR=/app/output
```

Save and exit: `Ctrl+X` → `Y` → `Enter`

**Confirm no placeholders remain:**
```bash
grep '<' agent/.env.rag
# Should return nothing
```

✅ **Done when:** No angle-bracket placeholders remain in the file.

---

### Step 2 — Start the Stack

```bash
sudo docker compose -f docker-compose-rag.yml up -d
```

**Check that all four containers are running:**
```bash
sudo docker compose -f docker-compose-rag.yml ps
```

✅ **Done when:**

```
NAME                        STATUS
ollama                      Up (healthy)
log-analyst-rag             Up
log-analyst-dashboard       Up
open-webui                  Up (healthy)
```

> ⚠️ If a container shows `Exited`, check its logs before going further:
> ```bash
> sudo docker logs <container-name> --tail 30
> ```

---

### Step 3 — Pull the AI Models

Ollama is running but empty. Pull all three models now:

```bash
# Large reasoning model — ~5GB — go get a coffee
sudo docker exec ollama ollama pull llama3.1:8b

# Small query generation model — ~2GB
sudo docker exec ollama ollama pull llama3.2:3b

# Embedding model for RAG — ~270MB, fast
sudo docker exec ollama ollama pull nomic-embed-text
```

> You can watch GPU memory fill up in another terminal while models load:
> ```bash
> watch -n 2 nvidia-smi
> ```

**Confirm all three are present:**
```bash
sudo docker exec ollama ollama list
```

✅ **Done when:**

```
NAME                    SIZE
llama3.1:8b             4.7 GB
llama3.2:3b             2.0 GB
nomic-embed-text        274 MB
```

---

### Step 4 — Smoke Test

Three quick checks to confirm every layer is working.

**Agent API:**
```bash
curl -s -X POST http://localhost:7000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "what are the top source IPs in the firewall logs?"}]}' \
  | python3 -m json.tool | head -20
```

**Dashboard:**
```bash
curl -s http://localhost:5000 | grep -o "<title>.*</title>"
```

**OpenWebUI:**
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8080
# Should print: 200
```

✅ **Done when:** The API returns JSON with `"mode": "query"` and real IP addresses, the dashboard returns its title, and OpenWebUI returns `200`.

---

## 🎉 You're Up

Open a tunnel from your **local machine** to access the interfaces in your browser:

```bash
# Run this on YOUR LOCAL MACHINE
ssh -i ~/.ssh/IL6-Zero-Trust-Key.pem \
  -L 8080:10.40.0.90:8080 \
  -L 5000:10.40.0.90:5000 \
  -L 7000:10.40.0.90:7000 \
  ec2-user@<bastion-public-ip> \
  -N
```

| Interface | URL | What to do here |
|---|---|---|
| **OpenWebUI** | http://localhost:8080 | Ask questions about the logs |
| **Dashboard** | http://localhost:5000 | Browse reports, view raw queries |
| **API Docs** | http://localhost:7000/docs | Swagger UI and health check |

**Try your first question in OpenWebUI:**
```
What are the top 5 source IPs by connection count?
```

---

## 🔧 Troubleshooting

### A container won't start or keeps restarting

```bash
sudo docker logs <container-name> --tail 50
```

Most common cause: a wrong or missing value in `agent/.env.rag`. Make sure the OpenSearch endpoint has no `https://` prefix and no trailing slash.

---

### OpenSearch returns 403 or connection refused

Your IAM credentials may have rotated. Refresh them and restart:

```bash
ROLE=$(curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/)
CREDS=$(curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/$ROLE)
export AWS_ACCESS_KEY_ID=$(echo $CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['AccessKeyId'])")
export AWS_SECRET_ACCESS_KEY=$(echo $CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['SecretAccessKey'])")
export AWS_SESSION_TOKEN=$(echo $CREDS | python3 -c "import sys,json; print(json.load(sys.stdin)['Token'])")
export AWS_DEFAULT_REGION=us-gov-west-1

sudo docker compose -f docker-compose-rag.yml restart log-analyst-rag
```

---

### Model returns empty or garbled results

Make sure all three models finished pulling and the agent had time to initialize:

```bash
sudo docker exec ollama ollama list
sudo docker logs log-analyst-rag --tail 20
```

If models are present but results are still wrong:
```bash
sudo docker compose -f docker-compose-rag.yml restart log-analyst-rag
```

---

### Code changes aren't taking effect after a rebuild

Python caches compiled bytecode inside the container. Clear it:

```bash
sudo docker exec log-analyst-rag find /app -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
sudo docker compose -f docker-compose-rag.yml restart log-analyst-rag
```

---

### GPU not being used — inference is very slow

```bash
# Check the runtime
sudo docker inspect ollama | grep -i runtime
# Should show: "Runtime": "nvidia"

# If not, reconfigure and restart
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
sudo docker compose -f docker-compose-rag.yml restart ollama
```

---

## 📦 Reference

```
ECR image:  235856440647.dkr.ecr.us-gov-west-1.amazonaws.com/cnap-log-analyst-rag:v3
AMI:        ami-0a6d2fcf26f229fe1  (v3 — drivers and Docker pre-installed, skip C1–C4)
S3 archive: s3://cnap-dev-il6-ollama-knowledge-base-wgl/deployments/
GitLab:     https://gitlab.cce.af.mil/cloudone-operations-and-support/c1-ops-and-sustainment/
              cnap/engineering/il6-pioneers/ollama-openwebui-agent-wgl
```

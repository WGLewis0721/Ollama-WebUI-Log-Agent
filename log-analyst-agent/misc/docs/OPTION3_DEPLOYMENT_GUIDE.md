# Option 3: RAG-Enhanced Deployment Guide

Complete step-by-step guide to deploy the full RAG-enhanced log analyst system.

## 🎯 What You're Deploying

The complete production system:
- ✅ Fetch logs from AWS OpenSearch (Fluent Bit → OpenSearch)
- ✅ RAG context from your S3 documents (runbooks, docs, incidents)
- ✅ AI analysis with Llama 3.1 8B
- ✅ Web dashboard for team access
- ✅ Continuous monitoring

**Total cost: ~$122-130/month**

---

## 📋 Prerequisites Checklist

Before starting, ensure you have:

### AWS Resources:
- [ ] AWS OpenSearch cluster running
- [ ] Fluent Bit sending logs to OpenSearch
- [ ] OpenSearch index pattern (e.g., `logs-*`, `application-*`)
- [ ] EC2 instance (recommended: t3.xlarge or larger)
- [ ] S3 bucket created for knowledge base
- [ ] IAM role on EC2 with permissions for OpenSearch + S3

### Local Setup:
- [ ] SSH access to EC2 instance
- [ ] `log-analyst-agent-with-rag.tar.gz` file
- [ ] Your documentation/runbooks ready to upload

---

## 🔐 Step 1: Configure IAM Permissions

Your EC2 instance needs access to both OpenSearch and S3.

### Create IAM Policy

```bash
# Create policy file
cat > log-analyst-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpGet",
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpHead"
      ],
      "Resource": "arn:aws:es:*:*:domain/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:ListBucket",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR-BUCKET-NAME/*",
        "arn:aws:s3:::YOUR-BUCKET-NAME"
      ]
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name LogAnalystFullAccess \
  --policy-document file://log-analyst-policy.json
```

### Attach to EC2 Role

```bash
# If you don't have an IAM role yet, create one
aws iam create-role \
  --role-name LogAnalystEC2Role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ec2.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach policy
aws iam attach-role-policy \
  --role-name LogAnalystEC2Role \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/LogAnalystFullAccess

# Create instance profile
aws iam create-instance-profile --instance-profile-name LogAnalystEC2Role
aws iam add-role-to-instance-profile \
  --instance-profile-name LogAnalystEC2Role \
  --role-name LogAnalystEC2Role

# Attach to your EC2 instance
aws ec2 associate-iam-instance-profile \
  --instance-id i-YOUR_INSTANCE_ID \
  --iam-instance-profile Name=LogAnalystEC2Role
```

---

## 📦 Step 2: Prepare Your S3 Bucket

### Create S3 Bucket (if needed)

```bash
# Create bucket
aws s3 mb s3://your-company-knowledge-base --region us-east-1

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket your-company-knowledge-base \
  --versioning-configuration Status=Enabled
```

### Upload Your Documentation

```bash
# Example structure - adjust to your needs
mkdir -p knowledge-base/{runbooks,incidents,documentation,standards}

# Upload from local
aws s3 sync ./knowledge-base/ s3://your-company-knowledge-base/knowledge-base/

# Or copy from existing location
aws s3 cp s3://other-bucket/docs/ \
  s3://your-company-knowledge-base/knowledge-base/ \
  --recursive
```

### Example Documents to Include:

Create these if you don't have them yet:

```bash
# Example: Database troubleshooting runbook
cat > database-troubleshooting.md << 'EOF'
# Database Connection Troubleshooting

## Symptoms
- "Connection refused" errors
- "Too many connections" errors
- Timeouts on database queries

## Common Causes
1. Security group misconfiguration
2. Connection pool exhaustion
3. Database instance down or rebooting
4. Network connectivity issues

## Resolution Steps

### 1. Check Security Group
```bash
# Verify security group allows port 5432 (PostgreSQL) or 3306 (MySQL)
aws ec2 describe-security-groups --group-ids sg-YOUR_GROUP_ID
```

### 2. Check Connection Pool
```bash
# Review application logs for pool stats
kubectl logs deployment/api-service | grep "HikariPool"

# Restart to reset pool
kubectl rollout restart deployment/api-service
```

### 3. Check RDS Status
```bash
aws rds describe-db-instances \
  --db-instance-identifier your-db \
  --query 'DBInstances[0].[DBInstanceStatus,Endpoint]'
```

### 4. Verify Credentials
- Check AWS Secrets Manager for correct credentials
- Verify IAM database authentication if using it

## Prevention
- Set up CloudWatch alarms for connection count
- Configure connection pool properly (min: 5, max: 20)
- Enable enhanced monitoring on RDS

## Related Incidents
- INC-2024-031 (Jan 15, 2024) - Security group issue
- INC-2024-045 (Feb 3, 2024) - Connection pool exhaustion
EOF

# Upload to S3
aws s3 cp database-troubleshooting.md \
  s3://your-company-knowledge-base/knowledge-base/runbooks/
```

---

## 🖥️ Step 3: Deploy to EC2

### SSH into EC2

```bash
# SSH into your instance
ssh -i your-key.pem ubuntu@your-ec2-public-ip
```

### Upload and Extract Package

```bash
# From your local machine
scp -i your-key.pem log-analyst-agent-with-rag.tar.gz \
  ubuntu@your-ec2-public-ip:~

# On EC2
cd ~
tar -xzf log-analyst-agent-with-rag.tar.gz
cd log-analyst-agent
```

### Install Docker (if not already installed)

```bash
# Run deployment script (installs Docker + Docker Compose)
chmod +x deploy-ec2.sh
./deploy-ec2.sh
```

---

## ⚙️ Step 4: Configure the System

### Run Interactive Setup

```bash
chmod +x setup-rag.sh
./setup-rag.sh
```

### Setup Wizard Will Ask:

```
OpenSearch Endpoint: search-your-domain.us-east-1.es.amazonaws.com
AWS Region: us-east-1
S3 Bucket Name: your-company-knowledge-base
S3 Prefix: knowledge-base/
Number of context documents [3]: 5
Analysis type: 1 (general)
Enable continuous monitoring: Y
Check interval: 5 minutes
```

### Or Configure Manually:

```bash
# Create .env.rag file
cat > .env.rag << 'EOF'
# S3 Knowledge Base
S3_BUCKET_NAME=your-company-knowledge-base
S3_PREFIX=knowledge-base/

# OpenSearch
OPENSEARCH_ENDPOINT=search-your-domain.us-east-1.es.amazonaws.com
AWS_REGION=us-east-1
OPENSEARCH_INDEX=logs-*
TIME_RANGE_MINUTES=60

# RAG Settings
ENABLE_RAG=true
RAG_K=5

# Analysis
ANALYSIS_TYPE=general
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5

# Model
MODEL_NAME=llama3.1:8b

# Ollama
OLLAMA_BASE_URL=http://ollama:11434

# Dashboard
DASHBOARD_PORT=5000
EOF
```

---

## 🔍 Step 5: Enable OpenSearch k-NN

OpenSearch needs the k-NN plugin enabled for vector search.

### Check if k-NN is Already Enabled

```bash
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/_cluster/settings?include_defaults=true" \
  | grep knn
```

### Enable k-NN (if needed)

**Option A: AWS Console**
1. Go to AWS OpenSearch dashboard
2. Select your domain
3. Click "Edit domain"
4. Under "Advanced cluster settings"
5. Add: `knn.enabled = true`
6. Save changes (may take 5-10 minutes)

**Option B: AWS CLI**
```bash
aws opensearch update-domain-config \
  --domain-name your-opensearch-domain \
  --advanced-options knn.enabled=true
```

---

## 🚀 Step 6: Start the System

### Start Ollama First

```bash
# Start Ollama service
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d ollama

# Wait for it to be ready
sleep 10

# Verify it's running
docker ps | grep ollama
curl http://localhost:11434/api/tags
```

### Pull Required Models

```bash
# Pull LLM model (Llama 3.1 8B) - ~4.7GB
docker exec ollama ollama pull llama3.1:8b

# Pull embedding model (nomic-embed-text) - ~274MB
docker exec ollama ollama pull nomic-embed-text

# Verify models are ready
docker exec ollama ollama list
```

Expected output:
```
NAME                    SIZE
llama3.1:8b            4.7 GB
nomic-embed-text       274 MB
```

---

## 📚 Step 7: Index Your Documents

### Run Document Indexer

```bash
# Index all documents from S3
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer
```

This will:
1. ✅ Connect to S3 and fetch documents
2. ✅ Split documents into chunks (500 chars)
3. ✅ Generate embeddings (768-dim vectors)
4. ✅ Create OpenSearch index with k-NN
5. ✅ Store all chunks with embeddings

Expected output:
```
📚 Document Indexer for RAG
============================

🔧 Setting up RAG system...
📥 Pulling embedding model nomic-embed-text...
✓ Model ready

✓ Created index: knowledge-base

📄 Fetching documents from S3...
Processing 15 .md files...

📄 Indexing: runbooks/database-troubleshooting.md (8 chunks)
✓ Indexed 8 chunks

📄 Indexing: incidents/inc-2024-031.md (5 chunks)
✓ Indexed 5 chunks

...

✅ Indexing complete!
   Total chunks indexed: 127
```

### Verify Indexing

```bash
# Check stats
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats
```

### Test Search

```bash
# Test if search works
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm \
  indexer test "database connection error"
```

Expected output:
```
🔍 Testing search: 'database connection error'

Found 3 relevant chunks:

1. database-troubleshooting.md (score: 0.876)
   When encountering database connection errors, first check
   the security group configuration to ensure port 5432...

2. incident-2024-031.md (score: 0.812)
   Root cause was security group sg-abc123 not allowing
   traffic from application subnet...

3. architecture.md (score: 0.734)
   Database connections are pooled using HikariCP with
   max pool size of 20 connections...
```

---

## 🎯 Step 8: Start RAG-Enhanced Analysis

### Start All Services

```bash
# Start the full system
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d
```

This starts:
- ✅ Ollama (LLM inference)
- ✅ Log Analyst Agent (fetches logs + analyzes with RAG)
- ✅ Dashboard (web UI)

### Verify Services are Running

```bash
# Check all containers
docker-compose --env-file .env.rag -f docker-compose-rag.yml ps
```

Expected output:
```
NAME                    STATUS              PORTS
ollama                  Up 5 minutes        0.0.0.0:11434->11434/tcp
log-analyst-rag         Up 2 minutes        
log-analyst-dashboard   Up 2 minutes        0.0.0.0:5000->5000/tcp
```

### View Logs

```bash
# Watch agent logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f log-analyst-rag
```

You should see:
```
🤖 Log Analyst Agent Initialized
✓ OpenSearch integration enabled
✓ RAG system ready
🔍 Fetching logs from OpenSearch...
   Index: logs-*
   Time Range: Last 60 minutes
✓ Fetched 857 logs
🔍 Analyzing logs with llama3.1:8b...
💾 Analysis saved: /app/output/analysis_opensearch_20240204_153045.json
```

---

## 🌐 Step 9: Configure Security Group for Dashboard

Allow port 5000 for your team to access the dashboard.

### Add Inbound Rule

```bash
# Get your EC2 security group
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

# Add rule for port 5000
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 5000 \
  --cidr 10.0.0.0/8  # Adjust to your VPN/office network
```

---

## 🎨 Step 10: Access the Dashboard

### Get Your Dashboard URL

```bash
# Get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Dashboard URL: http://$PUBLIC_IP:5000"
```

### Open in Browser

Navigate to: `http://YOUR_EC2_PUBLIC_IP:5000`

You should see:
```
┌─────────────────────────────────────────┐
│  🤖 Log Analyst Dashboard               │
│─────────────────────────────────────────│
│                                         │
│  📊 Statistics                          │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐│
│  │ Total    │ │ General  │ │ Security││
│  │ Reports  │ │          │ │         ││
│  │    3     │ │    2     │ │    1    ││
│  └──────────┘ └──────────┘ └─────────┘│
│                                         │
│  📝 Recent Analyses                     │
│  ─────────────────────────────────────  │
│  analysis_opensearch_20240204.json      │
│  └─ Click to view full analysis         │
└─────────────────────────────────────────┘
```

### Click on a Report

You'll see RAG-enhanced analysis:
```
Summary
───────
System health: 3 critical issues detected in payment service

Critical Issues
───────────────
1. Database connection errors (45 occurrences)
   
   📚 From: database-troubleshooting.md
   ─────────────────────────────────────
   "When seeing connection errors:
   1. Check security group sg-abc123
   2. Verify max_connections in RDS
   3. Reset pool: kubectl rollout restart"
   
   💡 Recommended Action:
   Check security group configuration first

2. High memory usage (87% on api-service)
   
   📚 From: incident-2024-022-memory-leak.md
   ─────────────────────────────────────
   "Previous memory leak was caused by
   unclosed HTTP connections. Fixed by
   upgrading requests library to v2.31"
   
   💡 Recommended Action:
   Review HTTP connection handling

Recommendations
───────────────
1. Immediate: Check security group sg-abc123
2. Short-term: Review connection pool settings
3. Monitor: Set up CloudWatch alarm for memory
```

---

## ✅ Step 11: Validation Checklist

Verify everything is working:

### System Health
```bash
# All containers running
docker-compose --env-file .env.rag -f docker-compose-rag.yml ps

# Ollama models loaded
docker exec ollama ollama list

# OpenSearch k-NN enabled
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/_cluster/settings" | grep knn
```

### Data Flow
```bash
# Documents indexed
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats
# Should show: Total chunks: 100+

# Logs being fetched
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs log-analyst-rag | grep "Fetched"
# Should show: ✓ Fetched XXX logs

# Analysis reports generated
ls -lh output/
# Should show: analysis_*.json and analysis_*.txt files
```

### Dashboard
- [ ] Dashboard loads at http://YOUR_IP:5000
- [ ] Statistics show correct counts
- [ ] Reports list is populated
- [ ] Can click and view full analysis
- [ ] Analysis includes context from runbooks
- [ ] Download button works

### RAG Context
```bash
# Test search returns relevant docs
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm \
  indexer test "payment error"

# Should return relevant runbooks/docs
```

---

## 🔄 Step 12: Ongoing Operations

### Update Documents

When you add/update runbooks:

```bash
# 1. Upload to S3
aws s3 cp new-runbook.md s3://your-bucket/knowledge-base/runbooks/

# 2. Reindex
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer
```

### Change Configuration

```bash
# Edit settings
nano .env.rag

# Restart to apply changes
docker-compose --env-file .env.rag -f docker-compose-rag.yml restart log-analyst-rag
```

### View Logs

```bash
# All logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f

# Specific service
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f log-analyst-rag
```

### Stop/Start

```bash
# Stop all
docker-compose --env-file .env.rag -f docker-compose-rag.yml down

# Start all
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d
```

---

## 🚨 Troubleshooting

### Issue: Can't connect to OpenSearch

```bash
# Check IAM role
aws sts get-caller-identity

# Test OpenSearch access
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/_cluster/health"
```

**Fix:** Verify IAM role has OpenSearch permissions

### Issue: Can't access S3

```bash
# Test S3 access
aws s3 ls s3://your-bucket/knowledge-base/
```

**Fix:** Verify IAM role has S3 permissions

### Issue: k-NN not working

```bash
# Check if k-NN is enabled
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/knowledge-base/_settings"
```

**Fix:** Enable k-NN in OpenSearch domain settings

### Issue: No documents indexed

```bash
# Check S3 has documents
aws s3 ls s3://your-bucket/knowledge-base/ --recursive

# Check indexer logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs indexer
```

**Fix:** Verify documents exist in S3 and have correct extensions (.md, .txt)

### Issue: Dashboard not accessible

```bash
# Check container
docker ps | grep dashboard

# Check security group
aws ec2 describe-security-groups --group-ids YOUR_SG_ID
```

**Fix:** Add inbound rule for port 5000

### Issue: Analysis not including context

```bash
# Test RAG search
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm \
  indexer test "your search term"
```

**Fix:** Verify documents are indexed and search returns results

---

## 📊 Cost Monitoring

### Track Your Costs

```bash
# S3 storage
aws s3 ls s3://your-bucket/knowledge-base/ --recursive \
  --summarize --human-readable

# OpenSearch storage
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/_cat/indices/knowledge-base?v"

# EC2 instance
aws ec2 describe-instances --instance-ids YOUR_INSTANCE_ID \
  --query 'Reservations[0].Instances[0].InstanceType'
```

### Expected Monthly Costs

| Resource | Cost |
|----------|------|
| EC2 t3.xlarge | $120 |
| S3 (100GB docs) | $2-3 |
| OpenSearch | $0 (existing) |
| Data transfer | <$1 |
| **Total** | **~$122-130** |

---

## 🎉 Success!

You now have a **production-grade RAG-enhanced log analysis system**!

### What You've Built:
✅ AI-powered log analysis from OpenSearch  
✅ Company-specific insights from YOUR docs  
✅ Automated runbook references  
✅ Team dashboard with 24/7 access  
✅ Continuous monitoring every 5 minutes  
✅ All for ~$130/month  

### Share with Your Team:

```
Dashboard: http://YOUR_EC2_IP:5000

What it does:
- Monitors production logs automatically
- Provides AI analysis every 5 minutes
- References our runbooks for fixes
- Shows past incident solutions
- Available 24/7
```

---

## 📚 Next Steps

1. **Add more documentation** to S3
2. **Set up Slack notifications** (optional)
3. **Configure custom alerts** (optional)
4. **Schedule regular reindexing** (weekly recommended)
5. **Review and improve runbooks** based on AI insights

---

## 📞 Quick Commands

```bash
# View dashboard
http://YOUR_EC2_IP:5000

# Update docs
aws s3 sync ./docs/ s3://your-bucket/knowledge-base/
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer

# View logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f

# Restart
docker-compose --env-file .env.rag -f docker-compose-rag.yml restart

# Stop
docker-compose --env-file .env.rag -f docker-compose-rag.yml down

# Stats
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats
```

**Congratulations! You're running a production AI system!** 🚀

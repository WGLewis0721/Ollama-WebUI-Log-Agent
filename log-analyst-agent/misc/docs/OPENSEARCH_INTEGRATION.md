# OpenSearch Integration Guide

Complete guide for integrating the Log Analyst Agent with your Fluent Bit → AWS OpenSearch pipeline and providing team access to analysis reports.

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites](#prerequisites)
3. [AWS Configuration](#aws-configuration)
4. [Setup Instructions](#setup-instructions)
5. [Team Access](#team-access)
6. [Usage Examples](#usage-examples)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

```
┌──────────────┐
│ Applications │
└──────┬───────┘
       │ Logs
       ▼
┌──────────────┐
│ Fluent Bit   │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              AWS OpenSearch Cluster                      │
│  Indices: logs-*, application-*, kubernetes-*           │
└────────────────────────┬────────────────────────────────┘
                         │
                         │ Fetch logs
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     EC2 Instance                         │
│                                                          │
│  ┌────────────┐    ┌──────────────┐   ┌──────────────┐│
│  │  Ollama    │◄───┤ Log Analyst  │──►│  Dashboard   ││
│  │  (LLM)     │    │   Agent      │   │   (Web UI)   ││
│  └────────────┘    └──────────────┘   └──────┬───────┘│
│                                                │        │
│                           Output               │        │
│                              │                 │        │
│                              ▼                 ▼        │
│                    ┌──────────────────────────────┐    │
│                    │   Analysis Reports (JSON)    │    │
│                    └──────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                               │
                               │ Access via
                               ▼
                    ┌─────────────────┐
                    │  Team Members   │
                    │  (Web Browser)  │
                    └─────────────────┘
```

---

## ✅ Prerequisites

### 1. AWS OpenSearch Cluster
- Existing OpenSearch domain
- Fluent Bit configured to send logs
- Index pattern (e.g., `logs-*`, `application-*`)

### 2. EC2 Instance
- Ubuntu 20.04 or later
- Minimum: t3.large (2 vCPU, 8GB RAM)
- Recommended: g4dn.xlarge (GPU-accelerated)
- Docker and Docker Compose installed

### 3. IAM Permissions
- EC2 instance needs IAM role with OpenSearch access
- Required permissions:
  ```json
  {
    "Effect": "Allow",
    "Action": [
      "es:ESHttpGet",
      "es:ESHttpPost"
    ],
    "Resource": "arn:aws:es:REGION:ACCOUNT:domain/DOMAIN-NAME/*"
  }
  ```

---

## 🔧 AWS Configuration

### Step 1: Create IAM Role for EC2

```bash
# Create IAM policy for OpenSearch access
cat > opensearch-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpGet",
        "es:ESHttpPost",
        "es:ESHttpHead"
      ],
      "Resource": "arn:aws:es:*:*:domain/*"
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
  --policy-name LogAnalystOpenSearchAccess \
  --policy-document file://opensearch-policy.json

# Create IAM role
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

# Attach policy to role
aws iam attach-role-policy \
  --role-name LogAnalystEC2Role \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/LogAnalystOpenSearchAccess

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name LogAnalystEC2Role

aws iam add-role-to-instance-profile \
  --instance-profile-name LogAnalystEC2Role \
  --role-name LogAnalystEC2Role
```

### Step 2: Update OpenSearch Access Policy

In your OpenSearch domain access policy, add:

```json
{
  "Effect": "Allow",
  "Principal": {
    "AWS": "arn:aws:iam::YOUR_ACCOUNT_ID:role/LogAnalystEC2Role"
  },
  "Action": "es:*",
  "Resource": "arn:aws:es:REGION:ACCOUNT:domain/DOMAIN-NAME/*"
}
```

### Step 3: Launch EC2 with IAM Role

```bash
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.xlarge \
  --iam-instance-profile Name=LogAnalystEC2Role \
  --security-group-ids sg-YOUR_SG \
  --subnet-id subnet-YOUR_SUBNET \
  --key-name YOUR_KEY \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=log-analyst}]'
```

---

## 🚀 Setup Instructions

### 1. Deploy on EC2

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Clone or upload the project
cd /home/ubuntu
# (upload the log-analyst-agent.tar.gz file)
tar -xzf log-analyst-agent.tar.gz
cd log-analyst-agent

# Run deployment script
chmod +x deploy-ec2.sh
./deploy-ec2.sh
```

### 2. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.opensearch.example .env

# Edit with your OpenSearch details
nano .env

# Required settings:
# OPENSEARCH_ENDPOINT=search-your-domain.us-east-1.es.amazonaws.com
# AWS_REGION=us-east-1
# OPENSEARCH_INDEX=logs-*
```

### 3. Start the Services

```bash
# Use the OpenSearch-enabled compose file
docker-compose -f docker-compose-opensearch.yml up -d

# Check logs
docker-compose -f docker-compose-opensearch.yml logs -f
```

### 4. Verify Connection

```bash
# Test OpenSearch connection
docker-compose -f docker-compose-opensearch.yml exec log-analyst python -c "
from opensearch_integration import OpenSearchLogFetcher
import os
fetcher = OpenSearchLogFetcher(
    os.getenv('OPENSEARCH_ENDPOINT'),
    os.getenv('AWS_REGION')
)
logs = fetcher.fetch_logs(max_logs=10)
print(f'✓ Fetched {len(logs)} logs')
"
```

---

## 👥 Team Access

### Option 1: Web Dashboard (Recommended)

The built-in web dashboard provides a beautiful UI for your team to view reports.

**Access URL:** `http://your-ec2-ip:5000`

**Features:**
- 📊 Live statistics dashboard
- 📝 Browse all analysis reports
- 🔍 View detailed analysis
- ⬇️ Download reports
- 🔄 Auto-refresh every 30 seconds

**Setup Steps:**

```bash
# Dashboard is already running on port 5000
# Configure Security Group to allow port 5000

# Add inbound rule:
# Type: Custom TCP
# Port: 5000
# Source: Your team's IP range (e.g., 10.0.0.0/8 for VPN)
```

**Optional: Set up HTTPS with Nginx**

```bash
# Install Nginx
sudo apt-get install nginx certbot python3-certbot-nginx

# Create Nginx config
sudo nano /etc/nginx/sites-available/log-analyst

# Add configuration:
server {
    listen 80;
    server_name logs.your-domain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/log-analyst /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d logs.your-domain.com
```

### Option 2: Shared S3 Bucket

Upload reports to S3 for team access:

```bash
# Install AWS CLI on the EC2
pip install awscli

# Create upload script
cat > /home/ubuntu/upload-reports.sh << 'EOF'
#!/bin/bash
aws s3 sync /home/ubuntu/log-analyst-agent/output/ \
  s3://your-bucket/log-analysis-reports/ \
  --exclude "*" --include "*.json" --include "*.txt"
EOF

chmod +x /home/ubuntu/upload-reports.sh

# Add to cron (every 10 minutes)
crontab -e
# Add: */10 * * * * /home/ubuntu/upload-reports.sh
```

### Option 3: Slack Notifications

Send analysis summaries to Slack:

```bash
# Create Slack webhook notification script
cat > /home/ubuntu/log-analyst-agent/agent/slack_notify.py << 'EOF'
import os
import requests
import json
from pathlib import Path

SLACK_WEBHOOK = os.getenv('SLACK_WEBHOOK_URL')
OUTPUT_DIR = Path('/app/output')

def send_to_slack(report_file):
    with open(report_file, 'r') as f:
        report = json.load(f)
    
    message = {
        "text": "🤖 New Log Analysis Report",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Log Analysis Complete"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Type:* {report['analysis_type']}"},
                    {"type": "mrkdwn", "text": f"*Lines:* {report['log_lines']}"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": report['analysis'][:500] + "..."}
            }
        ]
    }
    
    requests.post(SLACK_WEBHOOK, json=message)

# Watch for new reports and send notifications
EOF
```

Add to docker-compose:
```yaml
environment:
  - SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

## 🎯 Usage Examples

### Example 1: Continuous Monitoring (Production)

```bash
# Edit .env
OPENSEARCH_INDEX=logs-production-*
TIME_RANGE_MINUTES=60
ANALYSIS_TYPE=general
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=15

# Start
docker-compose -f docker-compose-opensearch.yml up -d

# Team accesses: http://your-ec2-ip:5000
```

### Example 2: Security Audit

```bash
# Edit .env
OPENSEARCH_INDEX=logs-*
TIME_RANGE_MINUTES=1440  # Last 24 hours
ANALYSIS_TYPE=security
APPLICATION_NAME=api-gateway
WATCH_MODE=false

# Run one-time analysis
docker-compose -f docker-compose-opensearch.yml up log-analyst

# View results in dashboard
```

### Example 3: Application-Specific Analysis

```bash
# Edit .env
OPENSEARCH_INDEX=kubernetes-*
APPLICATION_NAME=payment-service
TIME_RANGE_MINUTES=30
ANALYSIS_TYPE=errors
ERRORS_ONLY=true

# Start monitoring
docker-compose -f docker-compose-opensearch.yml up -d
```

### Example 4: Performance Review

```bash
# Edit .env
OPENSEARCH_INDEX=app-logs-*
TIME_RANGE_MINUTES=120
ANALYSIS_TYPE=performance
WATCH_MODE=false

# Generate report
docker-compose -f docker-compose-opensearch.yml up log-analyst
```

---

## 🔍 Troubleshooting

### Issue: Cannot connect to OpenSearch

```bash
# Check IAM role is attached
aws ec2 describe-instances --instance-ids i-YOUR_INSTANCE_ID \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'

# Test connection from EC2
curl -XGET https://YOUR_OPENSEARCH_ENDPOINT/_cluster/health

# Check security groups allow HTTPS (443)
```

### Issue: No logs fetched

```bash
# Verify index pattern exists
docker-compose -f docker-compose-opensearch.yml exec log-analyst python -c "
from opensearch_integration import OpenSearchLogFetcher
import os
fetcher = OpenSearchLogFetcher(os.getenv('OPENSEARCH_ENDPOINT'), os.getenv('AWS_REGION'))
print(fetcher.client.cat.indices())
"

# Check time range (logs might be older than TIME_RANGE_MINUTES)
# Increase TIME_RANGE_MINUTES in .env
```

### Issue: Dashboard not accessible

```bash
# Check dashboard is running
docker-compose -f docker-compose-opensearch.yml ps

# Check port 5000 is open in security group
# Test locally
curl http://localhost:5000/health

# Check logs
docker-compose -f docker-compose-opensearch.yml logs dashboard
```

### Issue: Out of memory errors

```bash
# Use smaller model
# Edit .env: MODEL_NAME=llama3.2:3b

# Or upgrade EC2 instance to t3.xlarge or larger
```

---

## 🎉 Success Checklist

- [ ] EC2 instance has IAM role with OpenSearch access
- [ ] OpenSearch domain allows access from EC2
- [ ] Environment variables configured in `.env`
- [ ] Services running: `docker-compose ps` shows all healthy
- [ ] Logs being fetched: Check agent logs
- [ ] Analysis reports generated: `ls output/`
- [ ] Dashboard accessible: `http://your-ec2-ip:5000`
- [ ] Team members can access dashboard
- [ ] (Optional) Slack notifications working
- [ ] (Optional) S3 sync configured

---

## 📞 Need Help?

Common commands:
```bash
# View all logs
docker-compose -f docker-compose-opensearch.yml logs

# Restart services
docker-compose -f docker-compose-opensearch.yml restart

# Stop services
docker-compose -f docker-compose-opensearch.yml down

# Update configuration
nano .env
docker-compose -f docker-compose-opensearch.yml restart log-analyst

# Manual analysis
docker-compose -f docker-compose-opensearch.yml run --rm log-analyst python main_opensearch.py
```

Check the main README.md and ARCHITECTURE.md for more information.

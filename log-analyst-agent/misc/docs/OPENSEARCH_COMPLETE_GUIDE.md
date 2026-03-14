# Complete Solution: Fluent Bit → OpenSearch → Log Analyst Agent

## 🎯 What You're Getting

A fully integrated AI-powered log analysis system that:
1. **Fetches logs** from your AWS OpenSearch cluster (populated by Fluent Bit)
2. **Analyzes logs** using Llama 3.1 8B LLM
3. **Provides team access** via beautiful web dashboard
4. **Runs continuously** in watch mode on EC2

## 📊 Complete Architecture

```
┌────────────────┐
│ Your Apps      │
│ (Kubernetes,   │
│  Docker, etc.) │
└───────┬────────┘
        │
        │ stdout/stderr
        ▼
┌────────────────┐
│  Fluent Bit    │ ◄── Already configured
└───────┬────────┘
        │
        │ HTTP/HTTPS
        ▼
┌─────────────────────────────┐
│   AWS OpenSearch Cluster     │ ◄── Existing infrastructure
│   - Index: logs-*           │
│   - Retention: 7-30 days    │
└──────────────┬──────────────┘
               │
               │ Fetch logs via API
               │ (IAM authenticated)
               ▼
┌─────────────────────────────────────────────────────┐
│              EC2 Instance (t3.xlarge)                │
│                                                      │
│  ┌────────────────┐    ┌─────────────────────┐    │
│  │   Ollama       │◄───┤  Log Analyst Agent  │    │
│  │   (Llama 3.1)  │    │  - Fetch from OS    │    │
│  │                │    │  - Analyze w/ LLM   │    │
│  │                │    │  - Save reports     │    │
│  └────────────────┘    └─────────────────────┘    │
│                                                      │
│                         Reports                      │
│                            │                         │
│                            ▼                         │
│                    ┌──────────────┐                 │
│                    │  Dashboard   │◄────────────┐   │
│                    │  (Flask)     │             │   │
│                    │  Port: 5000  │             │   │
│                    └──────┬───────┘             │   │
│                           │                     │   │
└───────────────────────────┼─────────────────────┼───┘
                            │                     │
                            │ HTTP                │
                            │                     │
                            ▼                     │
                    ┌──────────────┐              │
                    │ Your Team    │──────────────┘
                    │ (Browser)    │   Auto-refresh
                    └──────────────┘
```

## 🚀 Quick Start (3 Steps)

### Step 1: Deploy to EC2

```bash
# SSH into your EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Upload and extract
scp log-analyst-agent.tar.gz ubuntu@your-ec2-ip:~
ssh ubuntu@your-ec2-ip
tar -xzf log-analyst-agent.tar.gz
cd log-analyst-agent

# Run deployment script
./deploy-ec2.sh
```

### Step 2: Configure OpenSearch

```bash
# Interactive setup wizard
./setup-opensearch.sh

# It will ask for:
# - OpenSearch endpoint
# - Index pattern (logs-*)
# - Time range
# - Analysis type
```

### Step 3: Access Dashboard

```bash
# Dashboard will be available at:
http://YOUR_EC2_PUBLIC_IP:5000
```

**That's it!** Your team can now access live log analysis reports.

---

## 📋 Detailed Setup

### Prerequisites Checklist

- [ ] AWS OpenSearch cluster running
- [ ] Fluent Bit sending logs to OpenSearch
- [ ] EC2 instance (t3.xlarge or larger)
- [ ] IAM role attached to EC2 with OpenSearch access
- [ ] Docker and Docker Compose installed

### IAM Role Configuration

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "es:ESHttpGet",
        "es:ESHttpPost"
      ],
      "Resource": "arn:aws:es:*:*:domain/YOUR_DOMAIN/*"
    }
  ]
}
```

Attach this policy to an IAM role and associate it with your EC2 instance.

### Environment Configuration

Key settings in `.env`:

```bash
# Your OpenSearch endpoint
OPENSEARCH_ENDPOINT=search-your-domain.us-east-1.es.amazonaws.com

# Index pattern from Fluent Bit
OPENSEARCH_INDEX=logs-*

# How far back to look
TIME_RANGE_MINUTES=60

# Analysis focus
ANALYSIS_TYPE=general  # or security, performance, errors

# Continuous monitoring
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5

# Model selection
MODEL_NAME=llama3.1:8b  # Best balance
```

---

## 👥 Team Access Methods

### Method 1: Web Dashboard (Recommended) ⭐

**URL:** `http://your-ec2-ip:5000`

**Features:**
- 📊 Real-time statistics
- 📝 Browse all analysis reports
- 🔍 View detailed analysis
- ⬇️ Download reports as text files
- 🔄 Auto-refresh every 30 seconds
- 📱 Mobile responsive

**Security Group Configuration:**
```
Type: Custom TCP
Port: 5000
Source: Your team's IP range (e.g., 10.0.0.0/8 for VPN)
```

**Optional HTTPS Setup:**
```bash
# Install Nginx and Certbot
sudo apt-get install nginx certbot python3-certbot-nginx

# Configure reverse proxy
sudo nano /etc/nginx/sites-available/log-analyst

# Add SSL certificate
sudo certbot --nginx -d logs.your-domain.com
```

### Method 2: Direct File Access

Reports are saved to `output/` directory:

```bash
# View latest report
ls -lth output/analysis_*.txt | head -1 | xargs cat

# Sync to S3 for team access
aws s3 sync output/ s3://your-bucket/log-reports/
```

### Method 3: Slack Integration

Get notifications in Slack:

```bash
# Add to docker-compose-opensearch.yml
environment:
  - SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
```

---

## 🎯 Use Cases & Examples

### Use Case 1: General Health Monitoring

**Goal:** Continuous health check of all applications

```bash
# .env configuration
OPENSEARCH_INDEX=logs-*
TIME_RANGE_MINUTES=60
ANALYSIS_TYPE=general
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=15
```

**What happens:**
- Every 15 minutes, agent fetches last hour of logs
- LLM analyzes for errors, warnings, patterns
- Report saved to dashboard
- Team sees latest system health status

### Use Case 2: Security Audit

**Goal:** Daily security review of API gateway logs

```bash
# .env configuration
OPENSEARCH_INDEX=api-logs-*
APPLICATION_NAME=api-gateway
TIME_RANGE_MINUTES=1440  # 24 hours
ANALYSIS_TYPE=security
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=1440  # Once per day
```

**What happens:**
- Once daily, analyzes 24h of API logs
- Identifies suspicious patterns, unauthorized access
- Team reviews security report each morning

### Use Case 3: Error Tracking

**Goal:** Real-time error monitoring for payment service

```bash
# .env configuration
OPENSEARCH_INDEX=kubernetes-*
APPLICATION_NAME=payment-service
TIME_RANGE_MINUTES=10
ERRORS_ONLY=true
ANALYSIS_TYPE=errors
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5
```

**What happens:**
- Every 5 minutes, fetches only ERROR/CRITICAL logs
- LLM identifies root causes and patterns
- Team gets quick insights when errors spike

### Use Case 4: Performance Analysis

**Goal:** Weekly performance review

```bash
# .env configuration
OPENSEARCH_INDEX=app-logs-*
TIME_RANGE_MINUTES=10080  # 1 week
ANALYSIS_TYPE=performance
WATCH_MODE=false
```

**What happens:**
- Run manually once per week
- Analyzes week's worth of logs for bottlenecks
- Team uses for sprint retrospectives

---

## 🎨 Dashboard Features

### Statistics Cards
- Total reports generated
- Analysis by type (general, security, performance, errors)
- Recent error count

### Reports List
- Chronological list of all analyses
- Color-coded by type
- Shows timestamp, model used, log count
- Click to view full report

### Report Details Modal
- Full AI analysis
- Metadata (time range, services analyzed)
- Download as text file
- Formatted for easy reading

### Auto-Refresh
- Dashboard updates every 30 seconds
- No manual refresh needed
- Always shows latest analysis

---

## 🔧 Configuration Options

### Model Selection

| Model | RAM | Speed | Use Case |
|-------|-----|-------|----------|
| llama3.2:3b | 4GB | ⚡ Fast | Dev/testing, high-volume |
| llama3.1:8b | 8GB | ⚡⚡ Medium | **Production (recommended)** |
| llama3:70b | 48GB+ | 🐌 Slow | Critical systems, best accuracy |

### Analysis Types

- **general**: Comprehensive overview (default)
- **security**: Focus on threats, unauthorized access
- **performance**: Bottlenecks, slow queries, resource issues
- **errors**: Deep-dive into exceptions and failures

### Watch Mode Settings

```bash
# Continuous monitoring
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5     # Check every 5 minutes

# One-time analysis
WATCH_MODE=false              # Run once and exit
```

---

## 📊 Resource Requirements

### EC2 Instance Recommendations

| Use Case | Instance Type | vCPU | RAM | Cost/Month* |
|----------|---------------|------|-----|-------------|
| Development | t3.large | 2 | 8GB | ~$60 |
| Production | t3.xlarge | 4 | 16GB | ~$120 |
| High-Volume | t3.2xlarge | 8 | 32GB | ~$240 |
| GPU-Accelerated | g4dn.xlarge | 4 | 16GB + GPU | ~$380 |

*Approximate costs for US East region

### OpenSearch Access Patterns

- Fetch frequency: Configurable (default: 5 minutes)
- Logs per fetch: Up to 1000 (configurable)
- Network traffic: ~1-5 MB per fetch
- Impact on OpenSearch: Minimal (read-only queries)

---

## 🚨 Troubleshooting

### Problem: Cannot connect to OpenSearch

```bash
# Check IAM role
aws ec2 describe-instances --instance-ids $(curl -s http://169.254.169.254/latest/meta-data/instance-id) \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'

# Test OpenSearch access
curl -XGET https://YOUR_OPENSEARCH_ENDPOINT/_cluster/health --aws-sigv4 "aws:amz:us-east-1:es"
```

### Problem: Dashboard not accessible

```bash
# Check dashboard is running
docker-compose -f docker-compose-opensearch.yml ps

# Check security group allows port 5000
aws ec2 describe-security-groups --group-ids YOUR_SG_ID

# View dashboard logs
docker-compose -f docker-compose-opensearch.yml logs dashboard
```

### Problem: No reports generated

```bash
# Check agent logs
docker-compose -f docker-compose-opensearch.yml logs log-analyst

# Verify logs are being fetched
docker-compose -f docker-compose-opensearch.yml exec log-analyst python -c "
from opensearch_integration import OpenSearchLogFetcher
import os
f = OpenSearchLogFetcher(os.getenv('OPENSEARCH_ENDPOINT'), os.getenv('AWS_REGION'))
logs = f.fetch_logs(index_pattern='logs-*', max_logs=10)
print(f'Fetched {len(logs)} logs')
"
```

---

## 📞 Quick Commands Reference

```bash
# Start everything
docker-compose -f docker-compose-opensearch.yml up -d

# View logs
docker-compose -f docker-compose-opensearch.yml logs -f

# Stop services
docker-compose -f docker-compose-opensearch.yml down

# Restart after config change
docker-compose -f docker-compose-opensearch.yml restart log-analyst

# Manual analysis run
docker-compose -f docker-compose-opensearch.yml run --rm log-analyst python main_opensearch.py

# Check dashboard
curl http://localhost:5000/health

# View latest report
ls -lt output/analysis_*.txt | head -1 | xargs cat
```

---

## ✅ Success Checklist

After setup, verify:

- [ ] Services running: `docker-compose -f docker-compose-opensearch.yml ps`
- [ ] Agent fetching logs: Check logs for "✓ Fetched X logs"
- [ ] Reports generated: `ls output/` shows .json and .txt files
- [ ] Dashboard accessible: Can open `http://your-ec2-ip:5000`
- [ ] Statistics showing: Dashboard shows correct report count
- [ ] Reports viewable: Can click and view full analysis
- [ ] Team can access: Other team members can reach dashboard

---

## 🎉 You're All Set!

Your team now has:
- ✅ AI-powered log analysis
- ✅ Beautiful web dashboard
- ✅ Continuous monitoring
- ✅ Automated insights
- ✅ No manual log digging!

**Dashboard URL:** `http://your-ec2-ip:5000`

**Next Steps:**
1. Bookmark the dashboard
2. Share URL with your team
3. Set up alerts/notifications (optional)
4. Review reports regularly
5. Adjust analysis type based on needs

Questions? Check the detailed docs:
- `OPENSEARCH_INTEGRATION.md` - Full setup guide
- `README.md` - General documentation
- `ARCHITECTURE.md` - Technical details

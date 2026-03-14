# Option 3: Quick Deployment Checklist

Use this checklist to deploy your RAG-enhanced log analyst in **30 minutes**.

## ✅ Pre-Deployment (5 min)

```bash
# 1. Verify AWS resources
□ OpenSearch cluster running
□ Fluent Bit sending logs
□ S3 bucket created
□ EC2 instance ready (t3.xlarge recommended)

# 2. Check access
□ Can SSH into EC2
□ EC2 has IAM role with OpenSearch + S3 access
□ Have documentation ready to upload
```

## ⚙️ Initial Setup (10 min)

```bash
# 3. Upload package to EC2
scp -i your-key.pem log-analyst-agent-with-rag.tar.gz ubuntu@YOUR_EC2_IP:~

# 4. Extract and setup
ssh -i your-key.pem ubuntu@YOUR_EC2_IP
tar -xzf log-analyst-agent-with-rag.tar.gz
cd log-analyst-agent

# 5. Install Docker (if needed)
./deploy-ec2.sh

# 6. Upload documentation to S3
aws s3 sync ./your-docs/ s3://your-bucket/knowledge-base/
```

## 🔧 Configuration (5 min)

```bash
# 7. Run setup wizard
./setup-rag.sh

# Provide when asked:
# - OpenSearch endpoint: search-domain.us-east-1.es.amazonaws.com
# - S3 bucket: your-company-knowledge-base
# - S3 prefix: knowledge-base/
# - Context docs: 5
# - Analysis type: general
# - Watch mode: Y
# - Interval: 5

# OR manually create .env.rag:
cat > .env.rag << 'EOF'
S3_BUCKET_NAME=your-company-knowledge-base
S3_PREFIX=knowledge-base/
OPENSEARCH_ENDPOINT=search-your-domain.us-east-1.es.amazonaws.com
AWS_REGION=us-east-1
OPENSEARCH_INDEX=logs-*
TIME_RANGE_MINUTES=60
ENABLE_RAG=true
RAG_K=5
ANALYSIS_TYPE=general
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5
MODEL_NAME=llama3.1:8b
OLLAMA_BASE_URL=http://ollama:11434
DASHBOARD_PORT=5000
EOF
```

## 🚀 Deployment (10 min)

```bash
# 8. Start Ollama
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d ollama
sleep 10

# 9. Pull models (this takes a few minutes)
docker exec ollama ollama pull llama3.1:8b      # ~4.7GB
docker exec ollama ollama pull nomic-embed-text  # ~274MB

# 10. Index documents
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer

# 11. Start all services
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d

# 12. Configure security group for port 5000
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
SG_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port 5000 \
  --cidr 10.0.0.0/8  # Adjust to your network
```

## ✅ Verification (2 min)

```bash
# 13. Check services
docker-compose --env-file .env.rag -f docker-compose-rag.yml ps

# Expected output:
# ollama                 Up
# log-analyst-rag        Up
# log-analyst-dashboard  Up

# 14. View logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f log-analyst-rag

# Look for:
# ✓ Fetched XXX logs
# ✓ RAG system ready
# 💾 Analysis saved

# 15. Test dashboard
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Dashboard: http://$PUBLIC_IP:5000"
# Open in browser - should see reports

# 16. Test RAG search
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm \
  indexer test "database error"

# Should return relevant runbooks

# 17. Check index stats
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats

# Should show: Total chunks: 100+
```

## 🎯 Success Criteria

Your deployment is successful when:

- [ ] All containers show "Up" status
- [ ] Dashboard accessible at http://YOUR_IP:5000
- [ ] Analysis reports visible in dashboard
- [ ] Reports include context from your runbooks
- [ ] RAG search returns relevant documents
- [ ] New reports generated every 5 minutes

## 📊 Expected Timeline

| Step | Time | Cumulative |
|------|------|------------|
| Pre-deployment checks | 5 min | 5 min |
| Upload & extract | 2 min | 7 min |
| Install Docker | 3 min | 10 min |
| Upload docs to S3 | 2 min | 12 min |
| Configuration | 3 min | 15 min |
| Start Ollama | 2 min | 17 min |
| Pull models | 5 min | 22 min |
| Index documents | 5 min | 27 min |
| Start services | 1 min | 28 min |
| Verification | 2 min | **30 min** |

## 🔥 One-Liner for Pros

If you have everything ready:

```bash
# Complete deployment in one command block
cd ~ && \
tar -xzf log-analyst-agent-with-rag.tar.gz && \
cd log-analyst-agent && \
cat > .env.rag << EOF
S3_BUCKET_NAME=your-bucket
S3_PREFIX=knowledge-base/
OPENSEARCH_ENDPOINT=search-domain.us-east-1.es.amazonaws.com
AWS_REGION=us-east-1
OPENSEARCH_INDEX=logs-*
TIME_RANGE_MINUTES=60
ENABLE_RAG=true
RAG_K=5
ANALYSIS_TYPE=general
WATCH_MODE=true
WATCH_INTERVAL_MINUTES=5
MODEL_NAME=llama3.1:8b
OLLAMA_BASE_URL=http://ollama:11434
DASHBOARD_PORT=5000
EOF
&& \
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d ollama && \
sleep 15 && \
docker exec ollama ollama pull llama3.1:8b && \
docker exec ollama ollama pull nomic-embed-text && \
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer && \
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d && \
echo "Dashboard: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):5000"
```

## 📞 Quick Commands Reference

```bash
# View dashboard
http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):5000

# View all logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f

# View agent logs only
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs -f log-analyst-rag

# Restart services
docker-compose --env-file .env.rag -f docker-compose-rag.yml restart

# Update configuration
nano .env.rag
docker-compose --env-file .env.rag -f docker-compose-rag.yml restart log-analyst-rag

# Add new documents
aws s3 cp new-doc.md s3://your-bucket/knowledge-base/runbooks/
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer

# Check stats
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats

# Test search
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm \
  indexer test "your search term"

# Stop everything
docker-compose --env-file .env.rag -f docker-compose-rag.yml down

# Complete restart
docker-compose --env-file .env.rag -f docker-compose-rag.yml down
docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d
```

## 🆘 Troubleshooting Quick Fixes

### No logs being fetched
```bash
# Check OpenSearch connection
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/_cluster/health"

# Verify IAM permissions
aws sts get-caller-identity
```

### Documents not indexed
```bash
# Check S3
aws s3 ls s3://your-bucket/knowledge-base/ --recursive

# Check indexer logs
docker-compose --env-file .env.rag -f docker-compose-rag.yml logs indexer
```

### Dashboard not accessible
```bash
# Check container
docker ps | grep dashboard

# Check security group
aws ec2 describe-security-groups --group-ids YOUR_SG
```

### RAG not working
```bash
# Verify k-NN enabled
curl -XGET "https://YOUR_OPENSEARCH_ENDPOINT/_cluster/settings" | grep knn

# Test search
docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm \
  indexer test "test"
```

## 📚 Detailed Guides

- **Full deployment:** See `OPTION3_DEPLOYMENT_GUIDE.md`
- **Architecture details:** See `RAG_COST_EFFECTIVE_GUIDE.md`
- **OpenSearch setup:** See `OPENSEARCH_COMPLETE_GUIDE.md`

## 🎉 You're Done!

Once all checkboxes are complete, you have:
- ✅ Production log analysis system
- ✅ RAG-enhanced with YOUR documentation
- ✅ Team dashboard for 24/7 access
- ✅ Continuous monitoring
- ✅ All for ~$130/month

**Share dashboard URL with your team and start getting AI-powered insights!** 🚀

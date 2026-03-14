#!/bin/bash

# RAG Setup Wizard
# Configure document indexing and RAG-enhanced log analysis

set -e

echo "📚 RAG Setup Wizard for Log Analyst"
echo "===================================="
echo ""

# Check if OpenSearch is configured
if [ -z "$OPENSEARCH_ENDPOINT" ]; then
    echo "📝 OpenSearch Configuration"
    read -p "OpenSearch Endpoint: " OPENSEARCH_ENDPOINT
    read -p "AWS Region [us-east-1]: " AWS_REGION
    AWS_REGION=${AWS_REGION:-us-east-1}
else
    echo "✓ Using existing OpenSearch configuration"
    AWS_REGION=${AWS_REGION:-us-east-1}
fi

echo ""
echo "📦 S3 Configuration"
read -p "S3 Bucket Name (for knowledge base): " S3_BUCKET_NAME

if [ -z "$S3_BUCKET_NAME" ]; then
    echo "❌ S3 bucket name is required"
    exit 1
fi

read -p "S3 Prefix [knowledge-base/]: " S3_PREFIX
S3_PREFIX=${S3_PREFIX:-knowledge-base/}

echo ""
echo "🧠 RAG Configuration"
read -p "Number of context documents to use [3]: " RAG_K
RAG_K=${RAG_K:-3}

echo ""
echo "📊 Analysis Configuration"
echo "1) general - Comprehensive analysis (default)"
echo "2) security - Security audit"
echo "3) performance - Performance analysis"
echo "4) errors - Error tracking"
read -p "Select analysis type [1]: " ANALYSIS_CHOICE
ANALYSIS_CHOICE=${ANALYSIS_CHOICE:-1}

case $ANALYSIS_CHOICE in
    1) ANALYSIS_TYPE="general" ;;
    2) ANALYSIS_TYPE="security" ;;
    3) ANALYSIS_TYPE="performance" ;;
    4) ANALYSIS_TYPE="errors" ;;
    *) ANALYSIS_TYPE="general" ;;
esac

echo ""
read -p "Enable continuous monitoring? [Y/n]: " WATCH_ENABLE
if [[ ! $WATCH_ENABLE =~ ^[Nn]$ ]]; then
    WATCH_MODE="true"
    read -p "Check interval in minutes [5]: " WATCH_INTERVAL
    WATCH_INTERVAL=${WATCH_INTERVAL:-5}
else
    WATCH_MODE="false"
    WATCH_INTERVAL="5"
fi

# Create .env file
echo ""
echo "💾 Creating .env.rag configuration..."

cat > .env.rag << EOF
# RAG Configuration
# ==================

# S3 Knowledge Base
S3_BUCKET_NAME=${S3_BUCKET_NAME}
S3_PREFIX=${S3_PREFIX}

# OpenSearch
OPENSEARCH_ENDPOINT=${OPENSEARCH_ENDPOINT}
AWS_REGION=${AWS_REGION}
OPENSEARCH_INDEX=logs-*
TIME_RANGE_MINUTES=60

# RAG Settings
ENABLE_RAG=true
RAG_K=${RAG_K}

# Analysis
ANALYSIS_TYPE=${ANALYSIS_TYPE}
WATCH_MODE=${WATCH_MODE}
WATCH_INTERVAL_MINUTES=${WATCH_INTERVAL}

# Model
MODEL_NAME=llama3.1:8b

# Ollama
OLLAMA_BASE_URL=http://ollama:11434

# Dashboard
DASHBOARD_PORT=5000

# Application Filter (optional)
APPLICATION_NAME=

# Errors Only (optional)
ERRORS_ONLY=false
EOF

echo "✓ Configuration saved to .env.rag"
echo ""

# Check if documents exist in S3
echo "🔍 Checking S3 bucket..."
if aws s3 ls s3://${S3_BUCKET_NAME}/${S3_PREFIX} --recursive 2>/dev/null | head -5; then
    echo "✓ Found documents in S3"
    DOC_COUNT=$(aws s3 ls s3://${S3_BUCKET_NAME}/${S3_PREFIX} --recursive | wc -l)
    echo "  Total files: $DOC_COUNT"
else
    echo "⚠️  No documents found in s3://${S3_BUCKET_NAME}/${S3_PREFIX}"
    echo ""
    read -p "Upload sample documents now? [y/N]: " UPLOAD_SAMPLES
    
    if [[ $UPLOAD_SAMPLES =~ ^[Yy]$ ]]; then
        mkdir -p ./sample-docs
        
        cat > ./sample-docs/database-troubleshooting.md << 'SAMPLE'
# Database Connection Troubleshooting

## Common Issues

### Connection Refused
1. Check security group allows port 5432
2. Verify RDS endpoint is correct
3. Check network ACLs

### Timeout Errors
1. Check connection pool settings
2. Verify RDS parameter group
3. Review slow query log

### Authentication Failed
1. Check credentials in AWS Secrets Manager
2. Verify IAM database authentication
3. Check user permissions

## Quick Fixes

### Restart Connection Pool
```bash
kubectl rollout restart deployment/api-service
```

### Check RDS Status
```bash
aws rds describe-db-instances --db-instance-identifier mydb
```
SAMPLE

        cat > ./sample-docs/incident-template.md << 'SAMPLE'
# Incident Report Template

## Incident Details
- Date: 
- Severity: 
- Services Affected: 
- Duration: 

## Timeline
- Detection: 
- Response: 
- Resolution: 

## Root Cause
[Describe what caused the incident]

## Resolution Steps
1. 
2. 
3. 

## Prevention Measures
[How to prevent this in the future]

## Related Runbooks
- 
SAMPLE

        aws s3 sync ./sample-docs/ s3://${S3_BUCKET_NAME}/${S3_PREFIX}
        echo "✓ Uploaded sample documents"
    fi
fi

echo ""
echo "📚 Next Steps"
echo "============"
echo ""
echo "1. Index your documents:"
echo "   docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer"
echo ""
echo "2. Test the index:"
echo "   docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats"
echo ""
echo "3. Test search:"
echo "   docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer test \"database error\""
echo ""
echo "4. Start RAG-enhanced analysis:"
echo "   docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d"
echo ""
echo "5. Access dashboard:"
echo "   http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_EC2_IP'):5000"
echo ""

read -p "Index documents now? [Y/n]: " INDEX_NOW
if [[ ! $INDEX_NOW =~ ^[Nn]$ ]]; then
    echo ""
    echo "🚀 Starting document indexing..."
    docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d ollama
    
    echo "⏳ Waiting for Ollama..."
    sleep 10
    
    echo "📥 Pulling embedding model (nomic-embed-text)..."
    docker exec ollama ollama pull nomic-embed-text
    
    echo "📚 Indexing documents..."
    docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer
    
    echo ""
    echo "✅ Indexing complete!"
    echo ""
    echo "📊 Index statistics:"
    docker-compose --env-file .env.rag -f docker-compose-rag.yml run --rm indexer stats
    
    echo ""
    read -p "Start RAG-enhanced analysis now? [Y/n]: " START_NOW
    if [[ ! $START_NOW =~ ^[Nn]$ ]]; then
        echo "🚀 Starting services..."
        docker-compose --env-file .env.rag -f docker-compose-rag.yml up -d
        
        echo ""
        echo "✅ RAG system is running!"
        echo ""
        echo "Dashboard: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_EC2_IP'):5000"
    fi
else
    echo ""
    echo "👍 Configuration complete!"
    echo "   Run the indexer when ready using the commands above."
fi

echo ""
echo "📖 For more information, see:"
echo "   - RAG_COST_EFFECTIVE_GUIDE.md"
echo "   - OPENSEARCH_COMPLETE_GUIDE.md"

#!/bin/bash

# Quick Setup Script for OpenSearch Integration
# This script helps configure the log analyst for OpenSearch

set -e

echo "🔧 Log Analyst Agent - OpenSearch Setup Wizard"
echo "==============================================="
echo ""

# Check if running on EC2
if ! curl -s -m 2 http://169.254.169.254/latest/meta-data/instance-id &>/dev/null; then
    echo "⚠️  Warning: Not running on EC2. IAM authentication may not work."
    echo "   Consider using AWS credentials in .env file for local testing."
    echo ""
fi

# Collect configuration
echo "📝 Please provide your OpenSearch configuration:"
echo ""

read -p "OpenSearch Endpoint (e.g., search-domain.us-east-1.es.amazonaws.com): " OPENSEARCH_ENDPOINT
read -p "AWS Region [us-east-1]: " AWS_REGION
AWS_REGION=${AWS_REGION:-us-east-1}

read -p "Index Pattern [logs-*]: " OPENSEARCH_INDEX
OPENSEARCH_INDEX=${OPENSEARCH_INDEX:-logs-*}

read -p "Time Range in Minutes [60]: " TIME_RANGE_MINUTES
TIME_RANGE_MINUTES=${TIME_RANGE_MINUTES:-60}

read -p "Application Name (optional, leave empty for all): " APPLICATION_NAME

echo ""
echo "🤖 Analysis Configuration:"
echo ""
echo "1) general     - Comprehensive analysis"
echo "2) security    - Security audit focus"
echo "3) performance - Performance bottlenecks"
echo "4) errors      - Error tracking"
read -p "Select Analysis Type [1]: " ANALYSIS_CHOICE
ANALYSIS_CHOICE=${ANALYSIS_CHOICE:-1}

case $ANALYSIS_CHOICE in
    1) ANALYSIS_TYPE="general" ;;
    2) ANALYSIS_TYPE="security" ;;
    3) ANALYSIS_TYPE="performance" ;;
    4) ANALYSIS_TYPE="errors" ;;
    *) ANALYSIS_TYPE="general" ;;
esac

echo ""
echo "📊 Model Selection:"
echo ""
echo "1) llama3.2:3b  - Fast, 4GB RAM (recommended for dev)"
echo "2) llama3.1:8b  - Balanced, 8GB RAM (recommended for production)"
echo "3) llama3:70b   - Best, 48GB+ RAM (requires GPU)"
read -p "Select Model [2]: " MODEL_CHOICE
MODEL_CHOICE=${MODEL_CHOICE:-2}

case $MODEL_CHOICE in
    1) MODEL_NAME="llama3.2:3b" ;;
    2) MODEL_NAME="llama3.1:8b" ;;
    3) MODEL_NAME="llama3:70b" ;;
    *) MODEL_NAME="llama3.1:8b" ;;
esac

echo ""
read -p "Enable continuous monitoring (watch mode)? [y/N]: " WATCH_ENABLE
if [[ $WATCH_ENABLE =~ ^[Yy]$ ]]; then
    WATCH_MODE="true"
    read -p "Check interval in minutes [5]: " WATCH_INTERVAL
    WATCH_INTERVAL=${WATCH_INTERVAL:-5}
else
    WATCH_MODE="false"
    WATCH_INTERVAL="5"
fi

# Create .env file
echo ""
echo "💾 Creating .env file..."
cat > .env << EOF
# OpenSearch Configuration
OPENSEARCH_ENDPOINT=${OPENSEARCH_ENDPOINT}
AWS_REGION=${AWS_REGION}
OPENSEARCH_INDEX=${OPENSEARCH_INDEX}
TIME_RANGE_MINUTES=${TIME_RANGE_MINUTES}
APPLICATION_NAME=${APPLICATION_NAME}
ERRORS_ONLY=false

# Model Configuration
MODEL_NAME=${MODEL_NAME}

# Analysis Configuration
ANALYSIS_TYPE=${ANALYSIS_TYPE}
WATCH_MODE=${WATCH_MODE}
WATCH_INTERVAL_MINUTES=${WATCH_INTERVAL}

# Ollama Configuration
OLLAMA_BASE_URL=http://ollama:11434

# Dashboard Configuration
DASHBOARD_PORT=5000

# Logging
LOG_LEVEL=INFO
OUTPUT_DIR=/app/output
EOF

echo "✅ Configuration saved to .env"
echo ""

# Test IAM role
echo "🔐 Checking IAM permissions..."
if aws sts get-caller-identity &>/dev/null; then
    echo "✅ AWS credentials available"
    IDENTITY=$(aws sts get-caller-identity --query 'Arn' --output text)
    echo "   Identity: $IDENTITY"
else
    echo "⚠️  AWS credentials not configured"
    echo "   Make sure EC2 instance has IAM role attached"
fi

echo ""
echo "🚀 Ready to deploy!"
echo ""
echo "Next steps:"
echo ""
echo "1. Review configuration:"
echo "   cat .env"
echo ""
echo "2. Start services:"
echo "   docker-compose -f docker-compose-opensearch.yml up -d"
echo ""
echo "3. Check logs:"
echo "   docker-compose -f docker-compose-opensearch.yml logs -f"
echo ""
echo "4. Access dashboard:"
echo "   http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_EC2_IP'):5000"
echo ""
echo "5. View analysis results:"
echo "   ls -lh output/"
echo ""

read -p "Start services now? [Y/n]: " START_NOW
if [[ ! $START_NOW =~ ^[Nn]$ ]]; then
    echo ""
    echo "🐳 Starting services..."
    docker-compose -f docker-compose-opensearch.yml up -d
    
    echo ""
    echo "⏳ Waiting for services to be ready..."
    sleep 10
    
    echo ""
    echo "📊 Service status:"
    docker-compose -f docker-compose-opensearch.yml ps
    
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "Dashboard: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo 'YOUR_EC2_IP'):5000"
    echo ""
    echo "View logs: docker-compose -f docker-compose-opensearch.yml logs -f"
else
    echo ""
    echo "👍 Configuration saved. Start services when ready:"
    echo "   docker-compose -f docker-compose-opensearch.yml up -d"
fi

#!/bin/bash

# Quick Start Script for Log Analyst Agent
# Run this script to quickly start analyzing logs

set -e

echo "🤖 Log Analyst Agent - Quick Start"
echo "=================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Run: curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed."
    exit 1
fi

# Check if logs directory has files
if [ -z "$(ls -A logs/*.log 2>/dev/null)" ]; then
    echo "⚠️  No log files found in logs/ directory"
    echo "📝 Creating example log file..."
    mkdir -p logs
    cat > logs/example.log << 'EOF'
2024-02-04 10:00:00 INFO Application started
2024-02-04 10:00:01 ERROR Failed to connect to database
2024-02-04 10:00:02 WARNING Retrying connection...
2024-02-04 10:00:03 INFO Database connected successfully
EOF
    echo "✓ Example log created: logs/example.log"
fi

echo ""
echo "📊 Configuration:"
echo "  Model: llama3.2:3b"
echo "  Analysis: general"
echo "  Watch Mode: disabled"
echo ""

# Ask user if they want to start
read -p "🚀 Start the analysis? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "🐳 Starting Docker containers..."
docker-compose up -d ollama

echo "⏳ Waiting for Ollama to be ready..."
sleep 10

echo "📥 Pulling model (this may take a few minutes on first run)..."
docker exec ollama ollama pull llama3.2:3b

echo "🔍 Running analysis..."
docker-compose up log-analyst

echo ""
echo "✅ Analysis complete!"
echo "📁 Check results in: ./output/"
echo ""
echo "Commands:"
echo "  View logs:    docker-compose logs log-analyst"
echo "  Re-analyze:   docker-compose up log-analyst"
echo "  Stop:         docker-compose down"
echo "  Watch mode:   Edit docker-compose.yml, set WATCH_MODE=true, then docker-compose up -d"

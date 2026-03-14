#!/bin/bash

# Log Analyst Agent - AWS EC2 Deployment Script
# This script automates the deployment process on a fresh EC2 instance

set -e  # Exit on error

echo "🚀 Starting Log Analyst Agent Deployment on AWS EC2"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running on Ubuntu/Debian
if [[ ! -f /etc/debian_version ]]; then
    echo -e "${RED}❌ This script is designed for Ubuntu/Debian systems${NC}"
    exit 1
fi

echo -e "\n${YELLOW}📦 Step 1: Updating system packages${NC}"
sudo apt-get update -qq
sudo apt-get upgrade -y -qq

echo -e "\n${YELLOW}🐳 Step 2: Installing Docker${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${GREEN}✓ Docker installed${NC}"
else
    echo -e "${GREEN}✓ Docker already installed${NC}"
fi

echo -e "\n${YELLOW}🔧 Step 3: Installing Docker Compose${NC}"
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    echo -e "${GREEN}✓ Docker Compose installed${NC}"
else
    echo -e "${GREEN}✓ Docker Compose already installed${NC}"
fi

# Check if NVIDIA GPU is present
echo -e "\n${YELLOW}🎮 Step 4: Checking for GPU${NC}"
if lspci | grep -i nvidia &> /dev/null; then
    echo -e "${GREEN}✓ NVIDIA GPU detected${NC}"
    
    echo -e "\n${YELLOW}📦 Step 5: Installing NVIDIA Docker Runtime${NC}"
    if ! command -v nvidia-smi &> /dev/null; then
        # Install NVIDIA drivers
        sudo apt-get install -y ubuntu-drivers-common
        sudo ubuntu-drivers autoinstall
        
        # Install NVIDIA Container Toolkit
        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
        curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | sudo tee /etc/apt/sources.list.d/nvidia-docker.list
        
        sudo apt-get update
        sudo apt-get install -y nvidia-container-toolkit
        sudo systemctl restart docker
        
        echo -e "${GREEN}✓ NVIDIA Docker Runtime installed${NC}"
        echo -e "${YELLOW}⚠️  System reboot required for GPU drivers. Run 'sudo reboot' after this script${NC}"
    else
        echo -e "${GREEN}✓ NVIDIA drivers already installed${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  No NVIDIA GPU detected. Will use CPU-based inference${NC}"
fi

echo -e "\n${YELLOW}📁 Step 6: Creating project directories${NC}"
mkdir -p ~/log-analyst-agent/{logs,output,config}
cd ~/log-analyst-agent

echo -e "\n${YELLOW}📋 Step 7: Creating configuration files${NC}"

# Create docker-compose.yml if not exists
if [ ! -f docker-compose.yml ]; then
    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "ollama", "list"]
      interval: 30s
      timeout: 10s
      retries: 3

  log-analyst:
    build:
      context: ./agent
      dockerfile: Dockerfile
    container_name: log-analyst
    depends_on:
      ollama:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs:ro
      - ./output:/app/output
      - ./config:/app/config
    environment:
      - OLLAMA_BASE_URL=http://ollama:11434
      - MODEL_NAME=llama3.2:3b
      - LOG_LEVEL=INFO
      - WATCH_MODE=false
      - ANALYSIS_TYPE=general
    restart: unless-stopped

volumes:
  ollama_data:
EOF
    echo -e "${GREEN}✓ docker-compose.yml created${NC}"
fi

echo -e "\n${YELLOW}🔐 Step 8: Configuring Security Group (Manual)${NC}"
echo -e "${YELLOW}Please ensure your EC2 Security Group allows:${NC}"
echo "  - Inbound: SSH (22) from your IP"
echo "  - Optional: Port 11434 if you want external Ollama API access"

echo -e "\n${GREEN}✅ Deployment script completed!${NC}"
echo ""
echo "=================================================="
echo "Next Steps:"
echo "=================================================="
echo "1. If GPU was detected, reboot: sudo reboot"
echo "2. Copy your agent code to ~/log-analyst-agent/agent/"
echo "3. Place log files in ~/log-analyst-agent/logs/"
echo "4. Start services: cd ~/log-analyst-agent && docker-compose up -d"
echo "5. Check logs: docker-compose logs -f"
echo "6. View results: ls -lh ~/log-analyst-agent/output/"
echo ""
echo "To enable GPU support:"
echo "  - Uncomment the GPU sections in docker-compose.yml"
echo "=================================================="

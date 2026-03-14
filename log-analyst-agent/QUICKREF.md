# Log Analyst Agent - Quick Reference Card

## 🚀 Quick Start (3 Steps)

```bash
# 1. Extract and navigate
tar -xzf log-analyst-agent.tar.gz
cd log-analyst-agent

# 2. Add your logs
cp /path/to/your/*.log logs/

# 3. Run
./start.sh
```

## 📋 Common Commands

### Development
```bash
# Start services
docker-compose up -d

# Run analysis
docker-compose up log-analyst

# View logs
docker-compose logs -f log-analyst

# Stop services
docker-compose down
```

### Using Makefile
```bash
make build          # Build images
make analyze        # Run analysis
make watch          # Continuous monitoring
make logs           # View logs
make clean          # Clean up
make test           # Test setup
```

### Direct Docker Commands
```bash
# Pull model manually
docker exec ollama ollama pull llama3.2:3b

# List models
docker exec ollama ollama list

# Interactive shell
docker-compose run --rm log-analyst bash
```

## 🔧 Configuration Quick Edit

```bash
# Edit docker-compose.yml
nano docker-compose.yml

# Common changes:
# - MODEL_NAME: llama3.2:3b → llama3.1:8b
# - ANALYSIS_TYPE: general → security
# - WATCH_MODE: false → true
```

## 📊 Analysis Types

```bash
# General analysis
ANALYSIS_TYPE=general

# Security audit
ANALYSIS_TYPE=security

# Performance issues
ANALYSIS_TYPE=performance

# Error debugging
ANALYSIS_TYPE=errors
```

## 🌐 AWS EC2 Deployment

```bash
# Initial setup
./deploy-ec2.sh

# Start services
docker-compose up -d

# Enable autostart
sudo cp log-analyst.service /etc/systemd/system/
sudo systemctl enable log-analyst
sudo systemctl start log-analyst
```

## 🔍 Troubleshooting One-Liners

```bash
# Check if Ollama is ready
curl http://localhost:11434/api/tags

# Restart everything
docker-compose restart

# Clean start
docker-compose down -v && docker-compose up -d

# View all container logs
docker-compose logs

# Check disk space
df -h

# Container resource usage
docker stats
```

## 📁 File Locations

```
logs/          → Input log files (.log)
output/        → Analysis results (.json, .txt)
agent/         → Application code
config/        → Configuration files
```

## 🎯 Model Choices

```bash
# Fast (4GB RAM)
MODEL_NAME=llama3.2:3b

# Balanced (8GB RAM)
MODEL_NAME=llama3.1:8b

# Accurate (48GB+ RAM)
MODEL_NAME=llama3:70b

# Alternative
MODEL_NAME=mistral:7b
```

## 💡 Pro Tips

```bash
# Analyze only recent logs
tail -n 1000 app.log > logs/recent.log

# Watch specific patterns
grep ERROR app.log > logs/errors.log

# Continuous monitoring
WATCH_MODE=true docker-compose up -d log-analyst

# Custom max lines
# Edit main.py: max_lines=2000
```

## 📞 Getting Help

```bash
# View README
cat README.md

# View Architecture
cat ARCHITECTURE.md

# Run tests
./test.sh

# Check service health
docker-compose ps
docker-compose logs
```

## 🔐 Production Checklist

- [ ] Configure AWS Security Groups
- [ ] Set up CloudWatch monitoring
- [ ] Enable log rotation
- [ ] Configure backup strategy
- [ ] Set up systemd service
- [ ] Test failure recovery
- [ ] Document custom configs
- [ ] Review disk space limits

## 🚨 Emergency Commands

```bash
# Stop everything immediately
docker-compose down

# Clean up disk space
docker system prune -a

# Reset to fresh state
docker-compose down -v
docker volume prune -f

# View system resources
docker stats --no-stream
free -h
df -h
```

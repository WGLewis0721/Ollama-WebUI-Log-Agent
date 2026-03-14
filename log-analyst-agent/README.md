# Log Analyst Agent 🤖

An intelligent log analysis agent powered by Ollama and LLMs, designed to automatically analyze application logs, identify issues, and provide actionable insights.

## Features ✨

- 🔍 **Intelligent Analysis**: Uses Ollama LLMs to understand log context and patterns
- 🎯 **Multiple Analysis Types**: General, Security, Performance, and Error-focused analysis
- 📊 **Pattern Detection**: Automatically identifies errors, warnings, exceptions, and HTTP status codes
- 📁 **Batch Processing**: Analyze multiple log files at once
- 👁️ **Watch Mode**: Continuous monitoring for production environments
- 🐳 **Docker-Ready**: Fully containerized for easy deployment
- 📝 **Detailed Reports**: JSON and human-readable text outputs

## Quick Start 🚀

### Prerequisites

- Docker and Docker Compose
- At least 4GB RAM (8GB+ recommended)
- Optional: NVIDIA GPU for faster inference

### 1. Clone and Setup

```bash
# Create project structure
mkdir -p logs config output

# Place your log files in the logs/ directory
cp /path/to/your/app.log logs/
```

### 2. Start the Services

```bash
# Start Ollama and the agent
docker-compose up -d

# Check logs
docker-compose logs -f log-analyst
```

The agent will:
1. Start Ollama service
2. Pull the LLM model (first run only)
3. Analyze all `.log` files in the `logs/` directory
4. Save results to `output/` directory

### 3. View Results

```bash
# Check the output directory
ls -lh output/

# View a readable analysis report
cat output/analysis_*.txt
```

## Configuration ⚙️

### Environment Variables

Edit `docker-compose.yml` to customize:

```yaml
environment:
  - MODEL_NAME=llama3.2:3b          # Options: llama3.2:3b, llama3.1:8b, mistral:7b
  - ANALYSIS_TYPE=general            # Options: general, security, performance, errors
  - WATCH_MODE=false                 # Set to true for continuous monitoring
  - LOG_LEVEL=INFO
```

### Analysis Types

- **general**: Comprehensive overview of all log aspects
- **security**: Focus on security incidents and unauthorized access
- **performance**: Identify bottlenecks and optimization opportunities
- **errors**: Deep dive into errors and exceptions

## Usage Examples 📚

### One-Time Analysis

```bash
# Analyze logs once and exit
docker-compose up log-analyst
```

### Continuous Monitoring

```bash
# Edit docker-compose.yml and set WATCH_MODE=true
# Then start the service
docker-compose up -d log-analyst

# View live logs
docker-compose logs -f log-analyst
```

### Security Audit

```bash
# In docker-compose.yml, set:
# ANALYSIS_TYPE=security

docker-compose up log-analyst
```

### Using Different Models

```bash
# For better accuracy (requires more resources)
# MODEL_NAME=llama3.1:8b

# For faster analysis (lower accuracy)
# MODEL_NAME=llama3.2:3b
```

## Project Structure 📂

```
log-analyst-agent/
├── docker-compose.yml          # Orchestration configuration
├── agent/
│   ├── Dockerfile             # Agent container definition
│   ├── main.py               # Main agent code
│   └── requirements.txt      # Python dependencies
├── logs/                     # Input: Place your log files here
├── output/                   # Output: Analysis results
│   ├── analysis_*.json      # Structured analysis data
│   └── analysis_*.txt       # Human-readable reports
└── config/                   # Optional: Custom configurations
```

## AWS EC2 Deployment 🌩️

### Recommended EC2 Instance Types

**Development:**
- t3.large (2 vCPU, 8GB RAM) - CPU-based models
- g4dn.xlarge (4 vCPU, 16GB RAM, 1 GPU) - GPU-accelerated

**Production:**
- t3.xlarge (4 vCPU, 16GB RAM) - CPU-based
- g4dn.2xlarge (8 vCPU, 32GB RAM, 1 GPU) - GPU-accelerated

### Setup on EC2

```bash
# Connect to your EC2 instance
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Clone your project
git clone <your-repo> log-analyst-agent
cd log-analyst-agent

# For GPU instances, enable GPU support in docker-compose.yml
# Uncomment the deploy.resources.reservations section

# Start the services
docker-compose up -d
```

### Production Best Practices

1. **Use GPU Instances**: For better performance with larger models
2. **Volume Management**: Mount EBS volumes for persistent logs
3. **Monitoring**: Set up CloudWatch for container health
4. **Security Groups**: Limit access to port 11434 (Ollama)
5. **Auto-scaling**: Use AWS Auto Scaling for dynamic workloads

## Performance Tuning 🔧

### Model Selection

| Model | Size | RAM Required | Speed | Accuracy |
|-------|------|--------------|-------|----------|
| llama3.2:3b | 3B | 4GB | Fast | Good |
| llama3.1:8b | 8B | 8GB | Medium | Better |
| llama3:70b | 70B | 48GB+ | Slow | Best |

### Optimizations

1. **Limit Log Lines**: Default is 1000 lines per file
2. **Batch Processing**: Analyze multiple files in one run
3. **GPU Acceleration**: Enable GPU support for faster inference
4. **Temperature**: Lower temperature (0.1-0.3) for more focused analysis

## Troubleshooting 🔧

### Model Pull Fails

```bash
# Manually pull the model
docker exec -it ollama ollama pull llama3.2:3b
```

### Out of Memory

```bash
# Use a smaller model
# Edit MODEL_NAME to llama3.2:3b in docker-compose.yml
```

### No Logs Analyzed

```bash
# Check if logs directory has .log files
ls logs/

# Check agent logs
docker-compose logs log-analyst
```

### Connection Refused

```bash
# Wait for Ollama to be ready
docker-compose logs ollama

# Restart services
docker-compose restart
```

## API Integration 🔌

You can also use the agent programmatically:

```python
from main import LogAnalystAgent

agent = LogAnalystAgent(
    ollama_url="http://localhost:11434",
    model_name="llama3.2:3b"
)

agent.ensure_model()

# Analyze a single log file
log_content = open("app.log").read()
analysis = agent.analyze_logs(log_content, analysis_type="security")

print(analysis['analysis'])
```

## Roadmap 🗺️

- [ ] REST API for remote analysis
- [ ] Slack/Discord notifications
- [ ] Custom analysis rules
- [ ] Log aggregation from multiple sources
- [ ] Real-time streaming analysis
- [ ] Web dashboard

## Contributing 🤝

Contributions welcome! Please feel free to submit issues and pull requests.

## License 📄

MIT License - feel free to use this in your projects!

## Support 💬

For issues and questions, please open a GitHub issue or contact the maintainers.

---

Built with ❤️ using Ollama and Python

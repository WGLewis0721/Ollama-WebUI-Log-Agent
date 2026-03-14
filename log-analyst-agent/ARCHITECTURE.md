# Log Analyst Agent - Architecture Documentation

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         AWS EC2 Instance                        │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │                    Docker Network                       │   │
│  │                                                         │   │
│  │   ┌──────────────┐              ┌──────────────┐      │   │
│  │   │   Ollama     │◄─────────────┤ Log Analyst  │      │   │
│  │   │  Container   │   REST API   │   Container  │      │   │
│  │   │              │              │              │      │   │
│  │   │ - LLM Model  │              │ - Python App │      │   │
│  │   │ - API Server │              │ - Log Parser │      │   │
│  │   └──────────────┘              └──────────────┘      │   │
│  │         │                              │               │   │
│  │         │                              │               │   │
│  │    ┌────▼──────┐                  ┌───▼────┐         │   │
│  │    │   Volume  │                  │ Volume │         │   │
│  │    │ ollama_data│                 │ /logs  │         │   │
│  │    └───────────┘                  └────────┘         │   │
│  │                                         │             │   │
│  └─────────────────────────────────────────┼─────────────┘   │
│                                             │                 │
│                                        ┌────▼─────┐          │
│                                        │ /output  │          │
│                                        │ (Results)│          │
│                                        └──────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Ollama Container
- **Purpose**: Hosts the LLM model and provides inference API
- **Image**: `ollama/ollama:latest`
- **Port**: 11434 (REST API)
- **Volume**: `ollama_data` for model storage
- **Resources**: 
  - CPU: 2-4 cores minimum
  - RAM: 4-8GB minimum (depends on model)
  - GPU: Optional but recommended

### 2. Log Analyst Container
- **Purpose**: Main application logic for log analysis
- **Base**: Python 3.11-slim
- **Dependencies**: ollama, requests, watchdog, pyyaml
- **Mounts**:
  - `/app/logs` - Input logs (read-only)
  - `/app/output` - Analysis results (read-write)
  - `/app/config` - Configuration files

### 3. Data Flow

```
┌─────────┐    Read    ┌───────────┐   Analyze   ┌─────────┐
│ Log     │──────────► │ Log       │───────────► │ Ollama  │
│ Files   │            │ Analyst   │             │ API     │
└─────────┘            └───────────┘             └─────────┘
                            │                          │
                            │                          │
                            ▼                          ▼
                       ┌────────────┐         ┌────────────┐
                       │ Parse &    │◄────────┤ LLM        │
                       │ Extract    │ Response│ Analysis   │
                       └────────────┘         └────────────┘
                            │
                            ▼
                       ┌────────────┐
                       │ Save       │
                       │ Results    │
                       └────────────┘
```

## Analysis Pipeline

### Phase 1: Log Ingestion
1. Read log files from `/app/logs`
2. Apply line limits (default: 1000 lines)
3. Handle encoding errors gracefully

### Phase 2: Pattern Extraction
```python
patterns = {
    'errors': regex_count(ERROR patterns),
    'warnings': regex_count(WARNING patterns),
    'exceptions': regex_count(Exception patterns),
    'critical': regex_count(CRITICAL patterns),
    'status_codes': {
        '4xx': count(4xx patterns),
        '5xx': count(5xx patterns)
    }
}
```

### Phase 3: AI Analysis
1. Create context-aware prompt with:
   - Log content (truncated to 8000 chars)
   - Pattern statistics
   - Analysis focus (general/security/performance/errors)

2. Send to Ollama API with parameters:
   - Temperature: 0.3 (focused analysis)
   - Max tokens: 1000

3. Receive structured analysis:
   - Summary
   - Critical Issues
   - Patterns
   - Recommendations

### Phase 4: Output Generation
1. **JSON Output** (`analysis_*.json`):
   - Timestamp
   - Model used
   - Analysis type
   - Patterns detected
   - Full analysis text
   - Metadata

2. **Human-Readable Output** (`analysis_*.txt`):
   - Formatted report
   - Pattern summary table
   - Analysis sections
   - Easy to read and share

## Configuration Options

### Environment Variables
| Variable | Default | Options | Description |
|----------|---------|---------|-------------|
| OLLAMA_BASE_URL | http://ollama:11434 | URL | Ollama API endpoint |
| MODEL_NAME | llama3.2:3b | Any Ollama model | LLM model to use |
| ANALYSIS_TYPE | general | general, security, performance, errors | Focus area |
| WATCH_MODE | false | true, false | Continuous monitoring |
| LOG_LEVEL | INFO | DEBUG, INFO, WARNING, ERROR | Logging verbosity |

### Model Selection Strategy

| Use Case | Model | RAM | Speed | Accuracy |
|----------|-------|-----|-------|----------|
| Quick scans | llama3.2:3b | 4GB | Fast | Good |
| Balanced | llama3.1:8b | 8GB | Medium | Better |
| Deep analysis | llama3:70b | 48GB+ | Slow | Best |

## Deployment Patterns

### Development Mode
```bash
# Single analysis
docker-compose up log-analyst

# Interactive
docker-compose run --rm log-analyst python
```

### Production Mode
```bash
# Continuous monitoring
WATCH_MODE=true docker-compose up -d log-analyst

# With systemd
sudo systemctl enable log-analyst
sudo systemctl start log-analyst
```

### Scaling Considerations

**Horizontal Scaling**:
- Run multiple analyst containers
- Partition logs by service/application
- Use load balancer for Ollama API

**Vertical Scaling**:
- Increase EC2 instance size
- Use GPU instances (g4dn, p3 families)
- Increase Ollama container resources

## Security Best Practices

1. **Network Isolation**
   - Use private Docker network
   - Restrict Ollama port (11434) externally
   - Use security groups/firewalls

2. **Log Sanitization**
   - Remove sensitive data before analysis
   - Use read-only mounts for logs
   - Implement log rotation

3. **Access Control**
   - Limit SSH access to EC2
   - Use IAM roles for AWS services
   - Rotate credentials regularly

4. **Monitoring**
   - CloudWatch for container health
   - Disk space monitoring
   - Alert on analysis failures

## Performance Optimization

### For CPU Instances
- Use smaller models (3B-8B parameters)
- Batch log analysis
- Limit log lines per file
- Schedule during off-peak hours

### For GPU Instances
- Enable GPU passthrough in Docker
- Use larger models (8B-70B parameters)
- Parallel processing of multiple logs
- Real-time analysis feasible

## Troubleshooting Guide

### Common Issues

**Issue**: Model download fails
**Solution**: 
```bash
docker exec ollama ollama pull llama3.2:3b
```

**Issue**: Out of memory
**Solution**: Use smaller model or increase instance RAM

**Issue**: Slow analysis
**Solution**: 
- Reduce log lines (`max_lines` parameter)
- Use GPU instance
- Switch to smaller model

**Issue**: No analysis output
**Solution**:
- Check log directory has .log files
- Verify container permissions
- Check Ollama API health

## Monitoring & Observability

### Key Metrics to Track
- Analysis time per log file
- Model inference latency
- Memory usage
- Disk I/O
- API error rate

### Logging Strategy
- Container logs: `docker-compose logs`
- Application logs: `/app/output/*.txt`
- System logs: CloudWatch Logs

## Future Enhancements

- [ ] REST API for remote analysis
- [ ] Web dashboard for results
- [ ] Slack/Discord notifications
- [ ] Custom analysis rules engine
- [ ] Multi-log correlation
- [ ] Streaming analysis
- [ ] Database integration
- [ ] Grafana dashboards

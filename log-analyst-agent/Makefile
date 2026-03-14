.PHONY: help build up down logs analyze clean pull-model restart watch status

# Default target
help:
	@echo "Log Analyst Agent - Available Commands"
	@echo "======================================"
	@echo "make build        - Build the Docker images"
	@echo "make up           - Start all services in background"
	@echo "make down         - Stop all services"
	@echo "make logs         - View agent logs"
	@echo "make analyze      - Run one-time analysis"
	@echo "make watch        - Start in watch mode (continuous monitoring)"
	@echo "make status       - Check service status"
	@echo "make pull-model   - Pull/update the LLM model"
	@echo "make restart      - Restart all services"
	@echo "make clean        - Remove containers and volumes"
	@echo "make test         - Run analysis on example logs"

# Build Docker images
build:
	docker-compose build

# Start services in background
up:
	docker-compose up -d
	@echo "✓ Services started. Run 'make logs' to view logs."

# Stop services
down:
	docker-compose down

# View logs
logs:
	docker-compose logs -f log-analyst

# Run one-time analysis
analyze:
	docker-compose up log-analyst

# Start in watch mode
watch:
	@echo "Starting in watch mode (continuous monitoring)..."
	docker-compose up -d log-analyst
	docker-compose logs -f log-analyst

# Check status
status:
	docker-compose ps

# Pull/update model
pull-model:
	docker-compose up -d ollama
	@sleep 5
	docker exec ollama ollama pull llama3.2:3b
	@echo "✓ Model updated"

# Restart services
restart:
	docker-compose restart

# Clean up
clean:
	docker-compose down -v
	@echo "✓ Containers and volumes removed"

# Test with example logs
test:
	@mkdir -p logs
	@if [ ! -f logs/example.log ]; then \
		echo "Creating example log file..."; \
		echo "2024-02-04 10:00:00 INFO Application started" > logs/example.log; \
		echo "2024-02-04 10:00:01 ERROR Database connection failed" >> logs/example.log; \
		echo "2024-02-04 10:00:02 WARNING Retrying connection..." >> logs/example.log; \
		echo "2024-02-04 10:00:03 INFO Connected successfully" >> logs/example.log; \
	fi
	@echo "Running test analysis..."
	docker-compose up log-analyst
	@echo "✓ Check results in ./output/"

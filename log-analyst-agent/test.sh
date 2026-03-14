#!/bin/bash

# Test Script for Log Analyst Agent
# Validates that everything is working correctly

set -e

echo "🧪 Log Analyst Agent - Test Suite"
echo "=================================="

FAILED=0
PASSED=0

# Helper functions
pass() {
    echo "✅ PASS: $1"
    ((PASSED++))
}

fail() {
    echo "❌ FAIL: $1"
    ((FAILED++))
}

# Test 1: Check Docker installation
echo ""
echo "Test 1: Docker Installation"
if command -v docker &> /dev/null; then
    pass "Docker is installed"
else
    fail "Docker is not installed"
fi

# Test 2: Check Docker Compose
echo ""
echo "Test 2: Docker Compose Installation"
if command -v docker-compose &> /dev/null; then
    pass "Docker Compose is installed"
else
    fail "Docker Compose is not installed"
fi

# Test 3: Check project structure
echo ""
echo "Test 3: Project Structure"
REQUIRED_DIRS=("agent" "logs" "output")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        pass "Directory exists: $dir"
    else
        mkdir -p "$dir"
        pass "Created directory: $dir"
    fi
done

REQUIRED_FILES=("docker-compose.yml" "agent/Dockerfile" "agent/main.py" "agent/requirements.txt")
for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        pass "File exists: $file"
    else
        fail "File missing: $file"
    fi
done

# Test 4: Create test log if needed
echo ""
echo "Test 4: Test Log File"
if [ ! -f "logs/test.log" ]; then
    cat > logs/test.log << 'EOF'
2024-02-04 10:00:00 INFO Test log file
2024-02-04 10:00:01 ERROR Test error message
2024-02-04 10:00:02 WARNING Test warning
EOF
    pass "Created test log file"
else
    pass "Test log file exists"
fi

# Test 5: Docker Compose validation
echo ""
echo "Test 5: Docker Compose Configuration"
if docker-compose config > /dev/null 2>&1; then
    pass "docker-compose.yml is valid"
else
    fail "docker-compose.yml has errors"
fi

# Test 6: Start services
echo ""
echo "Test 6: Starting Services"
docker-compose up -d ollama
sleep 5

if docker ps | grep -q ollama; then
    pass "Ollama container is running"
else
    fail "Ollama container failed to start"
fi

# Test 7: Check Ollama API
echo ""
echo "Test 7: Ollama API"
sleep 10  # Give Ollama time to start
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    pass "Ollama API is accessible"
else
    fail "Ollama API is not accessible"
fi

# Test 8: Pull model
echo ""
echo "Test 8: Model Download (this may take a few minutes)"
if docker exec ollama ollama pull llama3.2:3b > /dev/null 2>&1; then
    pass "Model downloaded successfully"
else
    fail "Failed to download model"
fi

# Test 9: Run analysis
echo ""
echo "Test 9: Running Analysis"
if docker-compose up --exit-code-from log-analyst log-analyst > /dev/null 2>&1; then
    pass "Analysis completed successfully"
else
    fail "Analysis failed"
fi

# Test 10: Check output
echo ""
echo "Test 10: Output Files"
if [ "$(ls -A output/*.json 2>/dev/null)" ]; then
    pass "Analysis output generated"
else
    fail "No analysis output found"
fi

# Summary
echo ""
echo "=================================="
echo "Test Summary"
echo "=================================="
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All tests passed! Your agent is ready to use."
    echo ""
    echo "Next steps:"
    echo "  1. Add your log files to ./logs/"
    echo "  2. Run: make analyze"
    echo "  3. Check results in ./output/"
    exit 0
else
    echo "⚠️  Some tests failed. Please review the errors above."
    exit 1
fi

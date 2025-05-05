#!/bin/bash

# Navigate to the docker directory
cd ../docker

# Copy .env file
cp ../.env .

# Build the base MCP image first
docker build -t mcp-base -f mcp/Dockerfile.base ..

# Build and start all services
docker-compose up -d

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Check service health
echo "Checking service health..."
curl -s http://localhost:8001/health || echo "Prometheus MCP is not healthy"
curl -s http://localhost:8002/health || echo "Grafana MCP is not healthy"
curl -s http://localhost:8003/health || echo "GitHub MCP is not healthy"

echo "Setup complete. Services are running at:"
echo "- Prometheus: http://localhost:9090"
echo "- Grafana: http://localhost:3000"
echo "- Prometheus MCP: http://localhost:8001"
echo "- Grafana MCP: http://localhost:8002"
echo "- GitHub MCP: http://localhost:8003"

FROM mcp-base

# Set environment variables
ENV PORT=8001 \
    PROMETHEUS_URL=http://prometheus:9090

# Expose port
EXPOSE 8001

# Copy Prometheus MCP server code
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

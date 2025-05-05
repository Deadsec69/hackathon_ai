FROM mcp-base

# Set environment variables
ENV PORT=8002 \
    GRAFANA_URL=http://grafana:3000 \
    GRAFANA_API_KEY=your-api-key

# Expose port
EXPOSE 8002

# Copy Grafana MCP server code
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

FROM mcp-base

# Set environment variables
ENV PORT=8003 \
    GITHUB_TOKEN="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" \
    GITHUB_OWNER="Deadsec69" \
    GITHUB_REPO="hackathon_ai"

# Expose port
EXPOSE 8003

# Copy GitHub MCP server code
COPY main.py .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y curl ca-certificates --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip and install with increased timeout
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout 1000 -r requirements.txt

COPY . .

EXPOSE 5001

# Start the FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5001"]

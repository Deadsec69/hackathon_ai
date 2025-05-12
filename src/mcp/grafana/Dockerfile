FROM python:3.11-slim

WORKDIR /app

# Upgrade pip and install with increased timeout
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --timeout 1000 -r requirements.txt

COPY . .

EXPOSE 5003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5003"]

# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set metadata
LABEL maintainer="Azure Batch JSON Processor"
LABEL description="Container for processing JSON data in Azure Batch with Managed Identity"
LABEL version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY processor/ ./processor/

# Create temp directory for file processing
RUN mkdir -p /tmp/batch_work

# Set Python path
ENV PYTHONPATH=/app

# Set entrypoint to Python
ENTRYPOINT ["python", "-u"]

# Default command: run main processor
CMD ["processor/main.py"]

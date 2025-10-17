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

# Create temp directory for file processing with proper permissions
RUN mkdir -p /tmp/batch_work && \
    chmod 777 /tmp/batch_work && \
    mkdir -p /app/temp && \
    chmod 777 /app/temp

# Set Python path
ENV PYTHONPATH=/app

# Create a startup script for better debugging
RUN echo '#!/bin/bash' > /app/start.sh && \
    echo 'echo "=== Container Starting ==="' >> /app/start.sh && \
    echo 'echo "Working Directory: $(pwd)"' >> /app/start.sh && \
    echo 'echo "Python Version: $(python --version)"' >> /app/start.sh && \
    echo 'echo "Python Path: $PYTHONPATH"' >> /app/start.sh && \
    echo 'echo "User ID: $(id)"' >> /app/start.sh && \
    echo 'echo "Contents of /app:"' >> /app/start.sh && \
    echo 'ls -la /app/' >> /app/start.sh && \
    echo 'echo "Contents of /app/processor:"' >> /app/start.sh && \
    echo 'ls -la /app/processor/ || echo "processor directory not found"' >> /app/start.sh && \
    echo 'echo "Directory permissions:"' >> /app/start.sh && \
    echo 'ls -ld /tmp/batch_work /app/temp /app 2>/dev/null || echo "Some directories not found"' >> /app/start.sh && \
    echo 'echo "=== Starting Python Application ==="' >> /app/start.sh && \
    echo 'exec python -u processor/main.py "$@"' >> /app/start.sh && \
    chmod +x /app/start.sh

# Set entrypoint to our startup script
ENTRYPOINT ["/app/start.sh"]

# Default command: no additional args
CMD []

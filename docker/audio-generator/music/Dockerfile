FROM nvidia/cuda:12.1.0-base-ubuntu22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies including Python
RUN apt-get update && apt-get install -y \
    python3.11 \
    python3.11-dev \
    python3-pip \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3 -m pip install --upgrade pip

WORKDIR /app

# Copy requirements
COPY requirements.txt /app/requirements.txt

# Install PyTorch with CUDA 12.1 support
RUN pip3 install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install Python dependencies
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY src/ /app/

# Environment variables
ENV PYTHONUNBUFFERED=1

# Expose HTTP API port
EXPOSE 8084

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8084/health || exit 1

# Run the service
CMD ["python3", "main.py"]

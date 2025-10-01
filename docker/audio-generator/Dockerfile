FROM nvidia/cuda:12.2.0-base-ubuntu22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # GStreamer for audio processing
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    # Python and development tools
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3-gi \
    python3-gst-1.0 \
    libgstreamer1.0-dev \
    gir1.2-gstreamer-1.0 \
    # FFmpeg for SRT streaming
    ffmpeg \
    # Audio libraries
    libsndfile1 \
    portaudio19-dev \
    # Utilities
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1

# Upgrade pip
RUN python3 -m pip install --upgrade pip

# Create directories
RUN mkdir -p /app /config /models /cache

# Set working directory
WORKDIR /app

# Copy requirements file
COPY src/requirements.txt /app/requirements.txt

# Install Python dependencies from requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Install PyTorch with CUDA support (larger package, separate layer)
RUN pip3 install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install AI model dependencies (will add specific models later)
# Placeholder for: chatterbox-tts, elevenlabs, mubert-api, etc.

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV GST_DEBUG=2
ENV CUDA_VISIBLE_DEVICES=0
ENV TRANSFORMERS_CACHE=/cache/transformers
ENV HF_HOME=/cache/huggingface

# Expose ports
# HTTP API
EXPOSE 8080
# SRT audio output channels
EXPOSE 9001/udp
EXPOSE 9002/udp
EXPOSE 9003/udp
EXPOSE 9004/udp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the application
CMD ["python3", "main.py"]

FROM nvidia/cuda:12.2.0-base-ubuntu22.04

# Avoid interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install GStreamer and dependencies
RUN apt-get update && apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3 \
    python3-pip \
    python3-gi \
    python3-gst-1.0 \
    libgstreamer1.0-dev \
    gir1.2-gstreamer-1.0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip3 install --no-cache-dir flask requests python-dotenv

# Create directories for volume mounts
RUN mkdir -p /app /config

# Set working directory
WORKDIR /app

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV GST_DEBUG=2

# Expose ports
EXPOSE 8080
EXPOSE 9000-9010/udp
EXPOSE 9998/udp

# Run the application
CMD ["python3", "main.py"]

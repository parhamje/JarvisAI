FROM python:3.11-slim

# Prevent interactive prompts during apt installation
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install system dependencies (FFmpeg, PortAudio, Xvfb for headless GUI/vision, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    portaudio19-dev \
    gcc \
    g++ \
    make \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    xvfb \
    x11vnc \
    fluxbox \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements_docker.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser dependencies
RUN playwright install chromium --with-deps || true

# Copy project files
COPY . /app

# Create output directories if needed
RUN mkdir -p /app/config /app/brain /root/Desktop/JarvisProjects

# Expose ports for WebSocket server (8765) and any web UI
EXPOSE 8765

# Start Xvfb virtual frame buffer + run main.py
CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x1024x24 & DISPLAY=:99 python main.py"]

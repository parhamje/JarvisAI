FROM python:3.11-slim-bookworm

# Prevent interactive prompts & force IPv4 for apt downloads
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4

# Install minimal essential dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    portaudio19-dev \
    git \
    curl \
    libgl1 \
    libglib2.0-0 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install python packages
COPY requirements_docker.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser only (chromium minimal)
RUN playwright install chromium || true

# Copy project files
COPY . /app

# Create output directories
RUN mkdir -p /app/config /app/brain /root/Desktop/JarvisProjects

EXPOSE 8765

CMD ["sh", "-c", "Xvfb :99 -screen 0 1280x1024x24 & DISPLAY=:99 python main.py"]

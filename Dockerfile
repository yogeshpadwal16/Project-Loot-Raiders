# Production Dockerfile for Project Loot Raiders
# Base image includes Ubuntu 22.04 LTS and required Playwright system dependencies
FROM mcr.microsoft.com/playwright:v1.44.0-jammy

# Environment settings
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install python3-pip, python3-dev, git, xvfb, and system tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-dev \
    git \
    xvfb \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Upgrade core pip tools
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy requirement files first for layer caching
COPY requirements.txt .

# Install python dependencies
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Pre-install Chromium browser binaries required by rebrowser-playwright at build time.
# This bakes the binaries into the read-only image layer, eliminating runtime installation
# and resolving spawn ETXTBSY races completely.
RUN python3 -m rebrowser_playwright install --with-deps chromium \
    && chmod -R 755 /ms-playwright

# Configure Git safe directories inside container to prevent exit code 128
RUN git config --global --add safe.directory /app \
    && git config --global --add safe.directory '*'

# Copy project source code
COPY . .

# Expose Dashboard port
EXPOSE 5555

# Run the master engine
CMD ["xvfb-run", "--server-args=-screen 0 1280x720x24", "python3", "loot_scraper.py"]

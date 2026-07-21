# Use python-slim with Playwright dependencies pre-installed
FROM mcr.microsoft.com/playwright:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Copy requirement files first for caching
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project source code
COPY . .

# Expose Dashboard port
EXPOSE 5555

# Run the master engine
CMD ["python", "loot_scraper.py"]

# GrandmaScrape Docker Image
# Production-ready containerized deployment

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==1.7.1

# Copy poetry files
COPY pyproject.toml poetry.lock* ./

# Configure poetry to not create virtual env
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Install Playwright browsers (for browser scraping)
RUN playwright install --with-deps chromium

# Copy application code
COPY scraper/ ./scraper/
COPY README.md ./

# Create directories for data and exports
RUN mkdir -p /app/data /app/exports /app/cache

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV SCRAPER_DATA_DIR=/app/data
ENV SCRAPER_EXPORT_DIR=/app/exports
ENV SCRAPER_CACHE_DIR=/app/cache

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Default command: run API server
CMD ["python", "-m", "uvicorn", "scraper.api.rest_server:app", "--host", "0.0.0.0", "--port", "8000"]

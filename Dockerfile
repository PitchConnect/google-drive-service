FROM python:3.11-slim-bookworm

# Install curl for health checks with improved error handling
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Build argument for version
ARG SERVICE_VERSION=development
ENV SERVICE_VERSION=${SERVICE_VERSION}

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy and install Python dependencies first (better caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership to non-root user
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 5000

# Health check with improved error handling
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Use exec form for better signal handling
CMD ["python", "app.py"]

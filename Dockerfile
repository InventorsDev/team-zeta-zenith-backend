# Use Python 3.11 slim image as base
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

RUN pip install --user --no-cache-dir \
    torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    transformers>=4.41.0,<5.0.0 \
    tokenizers==0.19.1 \
    spacy==3.7.4

# Then install the rest
RUN pip install --user --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.11-slim

ENV PATH="/root/.local/bin:$PATH"
WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY . .

# Create directories for models and data
RUN mkdir -p models data logs

# Create non-root user for security
RUN mkdir -p models data logs \
    && groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
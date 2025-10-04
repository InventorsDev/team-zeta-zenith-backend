# Stage 1: Builder
FROM python:3.11-slim as builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install heavy pinned deps first (cached separately)
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && pip install transformers==4.41.2 tokenizers==0.19.1 spacy==3.7.4

# Install remaining dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt


# Stage 2: Final runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local /usr/local

# Copy app source
COPY . .

# Create non-root user
RUN mkdir -p models data logs \
    && groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

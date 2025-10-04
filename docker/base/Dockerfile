# docker/base/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /opt/ml-base

# system deps needed to install some wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && \
    rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch from PyTorch index first (pin versions)
RUN pip install --no-cache-dir \
    torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu

# Install other heavy packages that should be shared
RUN pip install --no-cache-dir \
    transformers==4.41.2 \
    tokenizers==0.19.1 \
    spacy==3.7.4 \
    sentence-transformers==5.1.0

# (optional) cleanup to keep image small
RUN apt-get purge -y --auto-remove build-essential || true && \
    rm -rf /var/lib/apt/lists/* /root/.cache/pip

# set a non-root user if you want runtime security (optional)
RUN groupadd -r appuser && useradd -r -g appuser appuser

# default python-related files remain in /usr/local

# Winston development and CLI image
FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    WINSTON_DATA_DIR=/workspace/.winston \
    WINSTON_OFFLINE_MODE=true

WORKDIR /workspace

# System packages useful for Git fixture inspection and health checks
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        curl \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install package metadata first for better layer caching
COPY pyproject.toml README.md ./
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY profiles ./profiles
COPY registry ./registry

RUN pip install --upgrade pip \
    && pip install -e ".[dev]"

# Keep the container alive for interactive / Dev Container use
CMD ["sleep", "infinity"]

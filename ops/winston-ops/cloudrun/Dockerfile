# Offline nightly / staging image for winston-ops (Cloud Run Job).
# Build and push to Artifact Registry in the winston-ops project only.

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY profiles ./profiles
COPY fixtures ./fixtures
COPY ops/winston-ops/scripts ./ops/winston-ops/scripts

RUN pip install --no-cache-dir -e .

ENV WINSTON_OFFLINE_MODE=true
ENV WINSTON_NIGHTLY_OUT=/tmp/nightly

ENTRYPOINT ["/bin/bash", "/app/ops/winston-ops/scripts/nightly_replay.sh"]

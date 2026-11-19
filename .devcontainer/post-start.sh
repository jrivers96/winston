#!/usr/bin/env bash
set -euo pipefail

# Re-check Postgres after container restarts
until PGPASSWORD=winston_dev pg_isready -h postgres -U winston -d winston >/dev/null 2>&1; do
  echo "Waiting for PostgreSQL..."
  sleep 1
done

echo "PostgreSQL is ready."

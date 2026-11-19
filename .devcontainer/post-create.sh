#!/usr/bin/env bash
set -euo pipefail

echo "Installing Winston in editable mode..."
pip install -e ".[dev]"

echo "Ensuring test database exists..."
PGPASSWORD=winston_dev psql \
  -h postgres \
  -U winston \
  -d winston \
  -tc "SELECT 1 FROM pg_database WHERE datname = 'winston_test'" \
  | grep -q 1 \
  || PGPASSWORD=winston_dev psql \
    -h postgres \
    -U winston \
    -d winston \
    -c "CREATE DATABASE winston_test;"

echo "Initializing Winston schema and directories..."
winston init

echo "Running doctor..."
winston doctor --profile synthetic

echo "Dev container ready. Try: winston doctor --profile synthetic"

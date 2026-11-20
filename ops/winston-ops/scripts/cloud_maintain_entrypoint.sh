#!/usr/bin/env bash
# Cloud Run entrypoint: init Winston schema then maintain --once --persist.
# Expects WINSTON_DATABASE_URL (Cloud SQL unix socket via /cloudsql mount).
set -euo pipefail

export WINSTON_OFFLINE_MODE="${WINSTON_OFFLINE_MODE:-true}"
export WINSTON_STAGING_OUT="${WINSTON_STAGING_OUT:-/tmp/staging}"
mkdir -p "$WINSTON_STAGING_OUT"

if [[ -z "${WINSTON_DATABASE_URL:-}" ]]; then
  echo "ERROR: WINSTON_DATABASE_URL is required"
  exit 1
fi

echo "==> winston init (migrations)"
winston init

echo "==> maintain --once --persist"
set +e
/app/ops/winston-ops/scripts/staging_maintain.sh
rc=$?
set -e
# Exit 2 = trust gaps found (expected signal); still persisted. Treat as success for Cloud Run.
if [[ "$rc" -eq 0 || "$rc" -eq 2 ]]; then
  exit 0
fi
exit "$rc"

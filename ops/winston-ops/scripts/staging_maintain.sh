#!/usr/bin/env bash
# Staging maintain loop: trust/SLA → durable Winston issues (requires Postgres).
# Offline by default. Do not point DATABASE_URL at Supercalc production.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

export WINSTON_OFFLINE_MODE="${WINSTON_OFFLINE_MODE:-true}"
PROFILE="${WINSTON_MAINTAIN_PROFILE:-supercalc_synthetic}"
OUT_DIR="${WINSTON_STAGING_OUT:-.winston/staging}"
mkdir -p "$OUT_DIR"

if [[ -z "${WINSTON_DATABASE_URL:-}" ]]; then
  echo "ERROR: Set WINSTON_DATABASE_URL to the winston-ops Cloud SQL URL."
  echo "       Prefer Secret Manager secret winston-staging-database-url after Terraform apply."
  exit 1
fi

echo "Running maintain --once --persist (profile=$PROFILE)..."
# Keep stderr visible in Cloud Logging; JSON report on stdout only.
set +e
winston maintain --once --profile "$PROFILE" --persist --format json \
  > "$OUT_DIR/maintain-report.json"
maintain_rc=$?
set -e
if [[ ! -s "$OUT_DIR/maintain-report.json" ]]; then
  echo "ERROR: maintain produced no report (exit=$maintain_rc)"
  exit "${maintain_rc:-1}"
fi
if [[ "$maintain_rc" -ne 0 && "$maintain_rc" -ne 2 ]]; then
  echo "ERROR: maintain failed (exit=$maintain_rc)"
  exit "$maintain_rc"
fi

python - <<PY
import json
from pathlib import Path
import os
import sys

out = Path(os.environ.get("WINSTON_STAGING_OUT", ".winston/staging"))
report = json.loads((out / "maintain-report.json").read_text())
print(json.dumps({
    "ok": report.get("ok"),
    "passed": report.get("passed"),
    "failed": report.get("failed"),
    "unknown": report.get("unknown"),
    "drafts": len(report.get("drafts") or []),
    "persisted": report.get("persisted"),
}, indent=2))
if not report.get("ok"):
    # Gaps are expected signal — exit 2 for schedulers; report still written.
    sys.exit(2)
print("Staging maintain OK")
PY

#!/usr/bin/env bash
# Copy the live profile template locally (gitignored). Does not invent names.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SRC="$ROOT/profiles/supercalc_live.yaml.example"
DST="$ROOT/profiles/supercalc_live.yaml"

if [[ ! -f "$SRC" ]]; then
  echo "ERROR: missing template $SRC"
  exit 1
fi

if [[ -f "$DST" ]]; then
  echo "OK: $DST already exists (leaving untouched)"
else
  cp "$SRC" "$DST"
  echo "Created $DST from template — fill real read-only mappings only"
fi

if command -v winston >/dev/null 2>&1; then
  echo "==> winston doctor --profile supercalc_live"
  winston doctor --profile supercalc_live -f json || true
else
  echo "NOTE: winston CLI not on PATH — skip doctor"
fi

echo
echo "Next: edit $DST with real Supercalc table/metric/index identities."
echo "Then: WINSTON_OFFLINE_MODE=false WINSTON_LIVE_SMOKE=1 winston live-smoke --profile supercalc_live"

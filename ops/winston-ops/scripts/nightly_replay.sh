#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

export WINSTON_OFFLINE_MODE=true
OUT_DIR="${WINSTON_NIGHTLY_OUT:-.winston/nightly}"
mkdir -p "$OUT_DIR"

echo "Replaying synthetic Supercalc case..."
winston replay --case supercalc-late-correction --offline --format json \
  > "$OUT_DIR/synthetic-report.json"

echo "Replaying recorded sample bundle..."
winston replay --bundle supercalc-stress-s2-correction --offline --format json \
  > "$OUT_DIR/recorded-report.json"

python - <<PY
import json
from pathlib import Path
import os
import sys

out = Path(os.environ.get("WINSTON_NIGHTLY_OUT", ".winston/nightly"))
reports = {
    "synthetic": json.loads((out / "synthetic-report.json").read_text()),
    "recorded": json.loads((out / "recorded-report.json").read_text()),
}
summary = {
    name: {
        "passed": r.get("passed"),
        "case": r.get("case"),
        "affected_indices": r.get("impact", {}).get("affected_indices"),
        "unrelated_excluded": r.get("impact", {}).get("unrelated_excluded"),
    }
    for name, r in reports.items()
}
(out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
failed = [n for n, s in summary.items() if not s["passed"]]
if failed:
    sys.exit(f"Nightly replay failures: {failed}")
print("Nightly offline replay OK")
PY

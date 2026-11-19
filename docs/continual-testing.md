# Continual testing

Winston tests Supercalc-shaped products in layers. Capability labels:

| Label | Meaning |
| --- | --- |
| `fixture-verified` | Offline synthetic / recorded fixtures only |
| `live-verified` | Opt-in read-only live smoke (Phase D; not enabled yet) |

## Phase A — PR gate

GitHub Actions (`.github/workflows/ci.yml`):

1. **Unit** — `pytest tests/unit` + DEMO and Supercalc golden verification
2. **Integration** — Postgres service + `pytest tests/integration -m integration`
3. **Offline demo** — `winston replay --case supercalc-late-correction --offline`

No Supercalc credentials. No network adapters.

## Phase B — Supercalc synthetic profile

- Profile: `profiles/supercalc_synthetic.yaml`
- Products (artificial only):
  - `STRESS` — breadth-like chain across S1–S5
  - `HEDGE_ARM` — depends on STRESS S3 (2× level)
  - `TRUST_UNRELATED` — constant series that must stay out of STRESS impact
- Case: `supercalc-late-correction`

```bash
winston replay --case supercalc-late-correction --offline
winston diagnose --index STRESS --date S3 --profile supercalc_synthetic
winston impact --change S2_Q_CORRECTION --through S5 --profile supercalc_synthetic
```

## Phase C — Recorded fixtures + nightly

- Schema: `fixtures/recorded/README.md` (`manifest`, `graph`, `evidence`, `expectations`)
- Sample: `fixtures/recorded/samples/supercalc-stress-s2-correction/`
- Recording redacts secrets and omits customer P&L
- Nightly: `.github/workflows/nightly.yml` + `ops/winston-ops/scripts/nightly_replay.sh`

```bash
winston record --case supercalc-late-correction --output .winston/fixtures/recorded/my-run
winston replay --bundle supercalc-stress-s2-correction --offline
./ops/winston-ops/scripts/nightly_replay.sh
```

## GCP (`winston-ops`)

Staging/nightly Cloud resources belong in a dedicated GCP project. See `ops/winston-ops/README.md` for the skeleton. Local Dev Container + GitHub Actions remain the default until that project is provisioned.

## Phase D — Opt-in live smoke

- Template: `profiles/supercalc_live.yaml.example` (empty slots — no invented production names)
- Copy to `profiles/supercalc_live.yaml` (gitignored) and fill real mappings
- Gate: `WINSTON_LIVE_SMOKE=1` and `WINSTON_OFFLINE_MODE=false`
- CLI: `winston live-smoke --profile supercalc_live`
- Doctor: `winston doctor --profile supercalc_live` lists missing contract fields
- CI: `.github/workflows/live-smoke.yml` is **workflow_dispatch only** (never on PRs)
- Labels: incomplete config → `live-template`; successful verified reads → `live-verified`
- Forbidden: mutate / trigger jobs / publish / remediate

```bash
winston doctor --profile supercalc_live
WINSTON_OFFLINE_MODE=false WINSTON_LIVE_SMOKE=1 winston live-smoke --profile supercalc_live
```

Without filled contracts/credentials, live-smoke exits informatively with a precise missing-configuration list.

## Phase E — Trust / SLA → issues + maintain

Offline Supercalc-shaped trust checks map gaps into Winston issue + obligation drafts. Unknown is never forced to pass.

Checks (`src/winston/checks/trust.py`):

| Check | Fail when |
| --- | --- |
| `freshness_sla` | Expected STRESS sessions missing |
| `stale_window` | Observation older than SLA hours |
| `coverage_gap` | Declared coverage below threshold |
| `unrelated_exclusion` | `TRUST_UNRELATED_*` leaks into STRESS impact |

```bash
# Healthy offline pass (exit 0)
winston maintain --once --profile supercalc_synthetic --no-persist

# Simulate a missing session → draft issues (exit 2)
winston maintain --once --inject-missing S5 --format json

# Persist drafts to Postgres (dedupe by fingerprint)
winston maintain --once --persist
```

Nightly also runs `maintain --once --no-persist` so a healthy synthetic trust loop is asserted without writing issues.

## Still ahead

- **Provision `winston-ops` GCP** — Cloud SQL / scheduler for staging nightly (skeleton in `ops/winston-ops/`)
- **Fill `profiles/supercalc_live.yaml`** — real read-only mappings only (never invent production names)

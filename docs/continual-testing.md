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

Staging/nightly Cloud resources belong in a dedicated GCP project. See `ops/winston-ops/README.md`.

Terraform defaults to `enable_resources=false` (no billable creates). Local Dev Container + GitHub Actions remain the default until that project exists and apply is explicitly approved.

```bash
./ops/winston-ops/scripts/provision_check.sh          # validate skeleton, no apply
./ops/winston-ops/scripts/bootstrap_live_profile.sh   # copy live template (gitignored)
./ops/winston-ops/scripts/nightly_replay.sh           # offline nightly stand-in
# After Cloud SQL exists:
# WINSTON_DATABASE_URL=... ./ops/winston-ops/scripts/staging_maintain.sh
```

## Phase D — Opt-in live smoke

Supercalc’s system of record is **Postgres** (`polymarket_gvf` on Cloud SQL
`adept-snow-481601-c6:us-central1:polymarket-gvf-db-small`). Live smoke uses a
read-only Postgres contract; Winston Cloud SQL remains separate agent state.

Mappings follow **polymarket-gvf** tables (not generic calc-ops lineage slots):
`discovered_index_definitions`, `indexes`, `integrity_checks`,
`hedge_alert_outcomes`, `risk_rollups`, `signals`.

- Template: `profiles/supercalc_live.yaml.example`
- Local filled profile: `profiles/supercalc_live.yaml` (gitignored)
- Gate: `WINSTON_LIVE_SMOKE=1` and `WINSTON_OFFLINE_MODE=false`
- CLI: `winston live-smoke --profile supercalc_live`
- Doctor: `winston doctor --profile supercalc_live`
- Datadog optional (`datadog.enabled: false`)
- CI: `.github/workflows/live-smoke.yml` is **workflow_dispatch only**
- Labels: incomplete → `live-template`; verified reads → `live-verified`
- Forbidden: mutate / trigger jobs / publish / remediate
- Network: private-IP Cloud SQL — use Cloud Run in `adept-snow` + `polymarket-gvf-connector` (see `ops/winston-ops/docs/supercalc-sql-access.md`); password in `winston-staging-supercalc-pg-password`
- Verify readonly: `./ops/winston-ops/scripts/verify_supercalc_readonly.sh`
- Deploy live-smoke (adept-snow Cloud Run): `./ops/winston-ops/scripts/deploy_live_smoke_job.sh`

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

- **Fill `profiles/supercalc_live.yaml`** — real read-only mappings only (never invent production names); use `bootstrap_live_profile.sh`
- **Push Cloud Run nightly image** — replace hello placeholder; see `ops/winston-ops/cloudrun/README.md`
- **Staging maintain `--persist`** — use Secret Manager `winston-staging-database-url` + `staging_maintain.sh`

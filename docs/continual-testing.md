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

## Still ahead

- **Phase D** — opt-in live smoke behind source contracts
- **Phase E** — schedule `maintain` and map Supercalc trust/SLA checks into Winston issues

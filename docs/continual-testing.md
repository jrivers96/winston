# Continual testing

Winston tests Supercalc-shaped products in layers. Capability labels:

| Label | Meaning |
| --- | --- |
| `fixture-verified` | Offline synthetic / recorded fixtures only |
| `live-verified` | Opt-in read-only live smoke (not in Phase A/B) |

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
  - Origin: S2 `q` 0→5 (displayed level unchanged, carry propagates)
  - Affected: STRESS S3–S5 + HEDGE_ARM
  - Excluded: TRUST_UNRELATED
  - `as_executed` history preserved (S5=105); corrected plan S5=110

```bash
winston replay --case supercalc-late-correction --offline
winston diagnose --index STRESS --date S3 --profile supercalc_synthetic
winston impact --change S2_Q_CORRECTION --through S5 --profile supercalc_synthetic
```

## GCP note

Continual staging/nightly jobs belong in a dedicated `winston-ops` GCP project (later phases). Local Dev Container + this CI remain the Phase A/B path.

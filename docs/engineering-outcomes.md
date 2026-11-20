# Outcomes for engineering leadership

Winston is an **operations / context agent** for Supercalc-shaped products. It is
not a quantitative analyst: it does not certify that live index formulas or
trading edges are numerically correct. Supercalc owns calculation quality;
Winston owns process integrity, lineage, trust gates, and controlled reachability.

## Positive outcomes (VP of Engineering)

### 1. Continuous proof the ops loop still works

CI, nightly offline replay, and scheduled `maintain` show that lineage, late-correction
impact, and trust gates still pass on a known Supercalc-shaped model. That is a
regression safety net for “did we break how we reason about corrections and impact?”

### 2. Early signal when trust properties break

Freshness, coverage, staleness, and “unrelated stayed out of impact” can become
durable **issues + obligations**—tracked work instead of a Slack scavenger hunt.
Today that path runs on the synthetic Supercalc profile (`supercalc_synthetic`)
with `--persist` into Winston agent Cloud SQL. The leadership shape is the same
once live SoR feeds those checks: gaps become tickets, not silent drift.

### 3. Safe live connectivity gate

Opt-in live-smoke proves Winston can reach Supercalc Postgres with a **read-only
allowlist**, without mutate / trigger / publish rights. Preferred path is Private
Service Connect from `winston-ops-sc` (see
[ops/winston-ops/docs/supercalc-sql-access.md](../ops/winston-ops/docs/supercalc-sql-access.md)).
Capability label `live-verified` means “ops agent can see SoR,” not “numbers are right.”

### 4. Shared, durable context

Winston agent state (issues, obligations, history) lives in **winston-ops Cloud SQL**,
separate from Supercalc `polymarket_gvf`. Institutional memory survives people and
time: what was checked, what failed, what is still open—without merging ops tickets
into the product database.

### 5. Clear ownership split

| Owner | Owns |
| --- | --- |
| **Winston** | Ops / trust / lineage / reachability; issue scaffolding |
| **Supercalc (product / quant)** | Whether calculations, hedges, and stress math are correct |

That reduces the risk of one agent pretending to do both and failing at both.

## What Winston does *not* deliver (yet)

- Certifying live Supercalc indexes, signals, or rollups are numerically correct
- Auto-escalating empty *legacy* tables (`signals`, `indexes`,
  `discovered_index_definitions`) into engineering tickets—those writers are idle
  in the current Supercalc cutover; live signal paths use other tables
- A web UI: reports are JSON (CLI, Cloud Run logs, `.winston/reports/`)

## Report examples

| Layer | How to produce / view |
| --- | --- |
| Golden / lineage replay | `winston replay --case supercalc-late-correction --offline --format json` |
| Diagnose / impact | `winston diagnose` / `winston impact` on `supercalc_synthetic` |
| Trust maintain (healthy) | `winston maintain --once --profile supercalc_synthetic --no-persist --format json` |
| Trust gap → draft | `winston maintain --once --inject-missing S5 --format json` |
| Live reachability | `./ops/winston-ops/scripts/deploy_live_smoke_ops.sh` (or job logs for `winston-staging-live-smoke`) |
| Scheduled persist | Cloud Run `winston-staging-maintain` (`0 */6 * * *` UTC) |

Offline examples can be regenerated into `.winston/reports/` (gitignored runtime data).

## Next step (product)

Wire live SoR (e.g. `integrity_checks`, `transition_signals` / stress surfaces—not
only retired GVF tables) into maintain trust contexts so **production** gaps create
the same issue drafts offline leadership already sees on synthetic data.

## Related docs

- [continual-testing.md](continual-testing.md) — CI / nightly / live-smoke / maintain layers
- [ops/winston-ops/docs/supercalc-sql-access.md](../ops/winston-ops/docs/supercalc-sql-access.md) — PSC + job deploy
- [README.md](../README.md) — authority split and quick start

# Source Contract Template (Supercalc Postgres)

Live Supercalc reads target **polymarket-gvf** Postgres, not Databricks.
Winston agent state stays in `winston-ops-sc` Cloud SQL.

Do not invent relation names — copy from `polymarket-gvf/storage/models.py`.

## Postgres connection

```yaml
postgres:
  host: ""              # private IP or Auth Proxy localhost
  port: 5432
  database: "polymarket_gvf"
  sslmode: "require"
  auth_method: "password"   # or iam / cloudsql_iam
  credential_provider: ""   # e.g. secret:winston-staging-supercalc-pg-password
  connection_name: ""       # project:region:instance
  private_ip_required: true
  read_only: true
```

## Required mappings

| Winston slot | Supercalc relation |
| --- | --- |
| `index_definitions` | `discovered_index_definitions` |
| `index_series` | `indexes` |
| `integrity_checks` | `integrity_checks` |
| `hedge_alert_outcomes` | `hedge_alert_outcomes` |
| `risk_rollups` | `risk_rollups` |
| `signals` | `signals` |

Column maps should use the real SQLAlchemy column names from those models.

## Optional Datadog

```yaml
datadog:
  enabled: false
```

Enable only when real metric names are known.

## Product indices (examples)

- `systemic_stress` — stress breadth index (often computed; series may appear in `indexes`)
- `hedge_windows` — `hedge_alert_outcomes`
- `trust_status` — integrity / trust surfaces

## Trust checks (live maintain)

Optional `trust_checks:` block maps SoR into Phase E/F checks:

| Slot | Check | Live source |
| --- | --- | --- |
| `freshness.index_name` + lookback | `freshness_sla` | Distinct dates from `indexes` |
| `stale_window.sla_hours` | `stale_window` | Latest `integrity_checks.run_ts` (fallback: series max timestamp) |
| `coverage.min_coverage_ratio` | `coverage_gap` | Series row count vs `discovered_index_definitions` count |
| `integrity` | `integrity_status` | Non-pass rows in `integrity_checks` |

```bash
WINSTON_OFFLINE_MODE=false WINSTON_LIVE_SMOKE=1 \
  winston maintain --once --profile supercalc_live --format json
```

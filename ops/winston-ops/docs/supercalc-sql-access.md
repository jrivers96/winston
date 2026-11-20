# Supercalc Postgres access from Winston

## What was set up

| Item | Value |
| --- | --- |
| Instance | `adept-snow-481601-c6:us-central1:polymarket-gvf-db-small` |
| Database | `polymarket_gvf` |
| Read-only user | `winston_readonly` |
| Password secret (winston-ops) | `winston-staging-supercalc-pg-password` |
| Password secret (adept-snow copy) | `winston-readonly-password` |
| IAM | `winston-nightly@winston-ops-sc` → `roles/cloudsql.client` on adept-snow |
| SELECT grants | `discovered_index_definitions`, `indexes`, `integrity_checks`, `hedge_alert_outcomes`, `risk_rollups`, `signals` |

Verify:

```bash
./ops/winston-ops/scripts/verify_supercalc_readonly.sh
```

## Why not Auth Proxy from a laptop / winston-ops VPC alone?

The instance is **private IP only** (`sql.restrictPublicIp`). Cloud SQL Auth Proxy defaults to public IP and fails; `--private-ip` only works if the client has a route into the Supercalc VPC’s private services range.

VPC peering from `winston-ops-sc` to `adept-snow` **does not** transitively reach Cloud SQL’s private service connection range.

## Recommended paths

1. **Preferred for live smoke:** deploy/run the Winston job in **`adept-snow-481601-c6`**:

```bash
./ops/winston-ops/scripts/deploy_live_smoke_job.sh
```

That builds `gcr.io/adept-snow-481601-c6/winston-live-smoke`, attaches
`polymarket-gvf-connector` + Cloud SQL instance, injects
`WINSTON_SUPERCALC_PG_PASSWORD` from `winston-readonly-password`, and executes
`winston live-smoke` (allowlisted SELECTs → `live-verified` on success).

2. **Later:** Private Service Connect endpoint for Cloud SQL into `winston-ops-sc`.

3. **Winston agent state** stays on `winston-ops-sc` Cloud SQL (`winston-staging-pg`) — never merge DBs.

## Re-grant SELECT

```bash
gcloud run jobs execute winston-grant-readonly \
  --project=adept-snow-481601-c6 --region=us-central1 --wait
```

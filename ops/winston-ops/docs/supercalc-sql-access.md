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

1. **Preferred for live smoke:** run Winston live-smoke / SQL probes as a Cloud Run Job in **`adept-snow-481601-c6`** with:
   - `run.googleapis.com/cloudsql-instances: adept-snow-481601-c6:us-central1:polymarket-gvf-db-small`
   - `vpc-access-connector: polymarket-gvf-connector`
   - DSN host: `/cloudsql/adept-snow-481601-c6:us-central1:polymarket-gvf-db-small`
   - user `winston_readonly` + password from Secret Manager

2. **Later:** Private Service Connect endpoint for Cloud SQL into `winston-ops-sc`, then Auth Proxy / Cloud Run there.

3. **Winston agent state** stays on `winston-ops-sc` Cloud SQL (`winston-staging-pg`) — never merge DBs.

## Re-grant SELECT

```bash
gcloud run jobs execute winston-grant-readonly \
  --project=adept-snow-481601-c6 --region=us-central1 --wait
```

# Supercalc Postgres access from Winston

## What was set up

| Item | Value |
| --- | --- |
| Instance | `adept-snow-481601-c6:us-central1:polymarket-gvf-db-small` |
| Database | `polymarket_gvf` |
| Read-only user | `winston_readonly` |
| Password secret (winston-ops) | `winston-staging-supercalc-pg-password` |
| Password secret (adept-snow copy) | `winston-readonly-password` |
| PSC | Enabled on Supercalc instance; auto-endpoint in `winston-staging-vpc` |
| PSC consumer IP | `10.20.0.3` (ACTIVE) |
| Service connection policy | `winston-staging-sql-scp` (`google-cloud-sql`) |
| SELECT grants | `discovered_index_definitions`, `indexes`, `integrity_checks`, `hedge_alert_outcomes`, `risk_rollups`, `signals` |

## Preferred path: PSC from winston-ops

Cross-project Private Service Connect — live-smoke runs in **winston-ops-sc** over the PSC IP:

```bash
./ops/winston-ops/scripts/deploy_live_smoke_ops.sh
```

Job: `winston-staging-live-smoke` → VPC connector `winston-stg-conn` → `10.20.0.3:5432` (sslmode=require).
Successful run sets `capability_label=live-verified`.

## Alternate path: Cloud Run in adept-snow

Still valid if you want unix-socket Auth Proxy in the producer VPC:

```bash
./ops/winston-ops/scripts/deploy_live_smoke_job.sh
```

## Why not Auth Proxy from a laptop / peering alone?

The instance is **private IP only** (`sql.restrictPublicIp`). Cloud SQL Auth Proxy defaults to public IP and fails; `--private-ip` only works if the client has a route into the Supercalc VPC’s private services range.

VPC peering from `winston-ops-sc` to `adept-snow` **does not** transitively reach Cloud SQL’s private service connection range — use **PSC** instead.

## Winston agent state (separate DB)

Scheduled maintain --persist against winston-ops Cloud SQL:

```bash
./ops/winston-ops/scripts/deploy_maintain_job.sh
```

| Item | Value |
| --- | --- |
| Job | `winston-staging-maintain` |
| Schedule | `0 */6 * * *` UTC |
| Instance | `winston-ops-sc:us-central1:winston-staging-pg` |
| Secret | `winston-staging-database-url` |

Never merge Winston agent DB with Supercalc `polymarket_gvf`.

## Re-grant SELECT

```bash
gcloud run jobs execute winston-grant-readonly \
  --project=adept-snow-481601-c6 --region=us-central1 --wait
```

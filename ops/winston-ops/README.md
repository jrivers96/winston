# winston-ops (GCP project skeleton)

Winston continual testing and staging run in a **dedicated GCP project**, separate from Supercalc production.

Local Dev Container + GitHub Actions remain the default runners until this project is created and `enable_resources=true` is applied.

## Intended layout

| Resource | Purpose |
| --- | --- |
| Cloud SQL (Postgres 16) | Staging Winston agent state (issues/obligations) |
| Secret Manager | DB URL + empty shells for future live-smoke credentials |
| Artifact Registry + Cloud Run Job | Nightly offline replay / staging maintain |
| Cloud Scheduler | Cron trigger for the nightly job (UTC) |
| GCS reports bucket | Nightly JSON summaries |

## Rules

- Do **not** put Winston agent state in the Supercalc production project
- Live smoke is opt-in and read-only (`WINSTON_LIVE_SMOKE=1`)
- Nightly default path is offline recorded/synthetic + maintain `--no-persist`
- Terraform defaults to `enable_resources=false` (validates config, creates nothing billable)
- Never invent Supercalc production table/metric names in live profiles

## Local stand-in (now)

```bash
# Offline nightly (synthetic + recorded + maintain)
./ops/winston-ops/scripts/nightly_replay.sh

# Validate Terraform skeleton (no apply)
./ops/winston-ops/scripts/provision_check.sh

# Copy live profile template locally (gitignored) — fill real names yourself
./ops/winston-ops/scripts/bootstrap_live_profile.sh
```

GitHub Actions:

- PR gate: `.github/workflows/ci.yml`
- Nightly: `.github/workflows/nightly.yml`
- Live smoke: `.github/workflows/live-smoke.yml` (workflow_dispatch only)

## Provision sequence

1. Create GCP project `winston-ops` (or your dedicated ops project ID); link billing
2. `cd ops/winston-ops/terraform`
3. `cp terraform.tfvars.example terraform.tfvars` and set `project_id`
4. `./ops/winston-ops/scripts/provision_check.sh`
5. When ready: set `enable_resources=true`, then `terraform plan` / `terraform apply` (explicit approval)
6. Build/push the Cloud Run image — see `cloudrun/README.md`
7. Optional durable maintain: set `DATABASE_URL` from Secret Manager and run `./scripts/staging_maintain.sh`
8. Fill `profiles/supercalc_live.yaml` with **real** read-only mappings before any live smoke

## Terraform

| File | Contents |
| --- | --- |
| `variables.tf` | `project_id`, `enable_resources` (default false), SQL/schedule knobs |
| `apis.tf` | SQL, Secret Manager, Storage, Run, Scheduler, IAM, Artifact Registry |
| `sql.tf` | Postgres 16 + `winston` DB + app user + `database-url` secret |
| `secrets.tf` | Empty live-smoke secret shells (no values) |
| `storage.tf` | Nightly reports bucket |
| `iam.tf` | `winston-nightly` SA with least privilege for offline staging |
| `scheduler.tf` | Artifact Registry + Cloud Run Job + Scheduler |
| `outputs.tf` | Connection names, bucket, next steps |

State backend is intentionally unset — add a remote backend in the winston-ops project after the state bucket exists.

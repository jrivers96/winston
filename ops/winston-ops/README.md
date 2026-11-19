# winston-ops (GCP project skeleton)

Winston continual testing and staging should run in a **dedicated GCP project**, separate from Supercalc production.

## Intended layout

| Resource | Purpose |
| --- | --- |
| Cloud SQL (Postgres) | Staging Winston agent state (issues/obligations) |
| Secret Manager | Read-only Supercalc credentials for future live smoke |
| Cloud Run Job / Cloud Build | Nightly recorded fixture replay |
| Artifact bucket | Nightly report JSON/Markdown |

## Rules

- Do **not** put Winston agent state in the Supercalc production project
- Live smoke (Phase D) is opt-in and read-only
- Nightly default path is offline recorded/synthetic replay (no network)

## Local stand-in (now)

Until GCP is provisioned, use GitHub Actions:

- PR gate: `.github/workflows/ci.yml`
- Nightly: `.github/workflows/nightly.yml`

```bash
./ops/winston-ops/scripts/nightly_replay.sh
```

## Terraform

`terraform/` contains a non-applied skeleton. Fill project IDs and enable APIs before `terraform apply`.

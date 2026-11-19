# Cloud Run Job image

Build from the **repository root** after Artifact Registry exists in `winston-ops`:

```bash
PROJECT_ID=winston-ops   # real dedicated ops project
REGION=us-central1
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/winston/winston-ops:nightly"

docker build -f ops/winston-ops/cloudrun/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"
```

Then update the Cloud Run Job container image (Terraform ignores image drift after first apply).

Default entrypoint runs offline `nightly_replay.sh` (synthetic + recorded + maintain `--no-persist`).

For durable issues against Cloud SQL, override the job command to:

```bash
./ops/winston-ops/scripts/staging_maintain.sh
```

and mount `WINSTON_DATABASE_URL` from Secret Manager (`winston-staging-database-url`).

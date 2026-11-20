#!/usr/bin/env bash
# Build + deploy scheduled maintain --persist against winston-ops Cloud SQL.
set -euo pipefail

: "${CLOUDSDK_PYTHON:=/Users/jonathanrivers/anaconda3/envs/py3.11/bin/python}"
export CLOUDSDK_PYTHON
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PROJECT="${WINSTON_OPS_PROJECT:-winston-ops-sc}"
REGION="${WINSTON_OPS_REGION:-us-central1}"
JOB="${WINSTON_MAINTAIN_JOB:-winston-staging-maintain}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/winston/winston-maintain:latest"
INSTANCE="${WINSTON_SQL_INSTANCE:-winston-ops-sc:us-central1:winston-staging-pg}"
CONNECTOR="${WINSTON_VPC_CONNECTOR:-winston-stg-conn}"
SA="${WINSTON_NIGHTLY_SA:-winston-nightly@${PROJECT}.iam.gserviceaccount.com}"
SCHEDULE="${WINSTON_MAINTAIN_SCHEDULE:-0 */6 * * *}"
SCHEDULER_JOB="${WINSTON_MAINTAIN_SCHEDULER:-winston-staging-maintain}"

echo "==> Cloud Build $IMAGE"
gcloud builds submit \
  --project="$PROJECT" \
  --config=ops/winston-ops/cloudrun/cloudbuild.maintain.yaml \
  --substitutions=_REGION="$REGION" \
  .

echo "==> Create/update Cloud Run job $JOB"
COMMON_ARGS=(
  --project="$PROJECT"
  --region="$REGION"
  --image="$IMAGE"
  --service-account="$SA"
  --vpc-connector="$CONNECTOR"
  --vpc-egress=private-ranges-only
  --set-cloudsql-instances="$INSTANCE"
  --set-secrets=WINSTON_DATABASE_URL=winston-staging-database-url:latest
  --set-env-vars=WINSTON_OFFLINE_MODE=true,WINSTON_STAGING_OUT=/tmp/staging,WINSTON_MAINTAIN_PROFILE=supercalc_synthetic
  --max-retries=0
  --task-timeout=900
  --memory=1Gi
  --cpu=1
)

if gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" "${COMMON_ARGS[@]}"
else
  gcloud run jobs create "$JOB" "${COMMON_ARGS[@]}"
fi

echo "==> Schedule $SCHEDULER_JOB ($SCHEDULE UTC)"
URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "$SCHEDULER_JOB" --project="$PROJECT" --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http "$SCHEDULER_JOB" \
    --project="$PROJECT" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --time-zone=UTC \
    --uri="$URI" \
    --http-method=POST \
    --oauth-service-account-email="$SA"
else
  gcloud scheduler jobs create http "$SCHEDULER_JOB" \
    --project="$PROJECT" \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --time-zone=UTC \
    --uri="$URI" \
    --http-method=POST \
    --oauth-service-account-email="$SA"
fi

# Scheduler needs run.developer (or invoker) on the job
gcloud run jobs add-iam-policy-binding "$JOB" \
  --project="$PROJECT" \
  --region="$REGION" \
  --member="serviceAccount:${SA}" \
  --role="roles/run.invoker" \
  >/dev/null

echo "==> Execute once now"
gcloud run jobs execute "$JOB" --project="$PROJECT" --region="$REGION" --wait

echo "Done. Scheduled $SCHEDULE UTC → $JOB (maintain --persist)."

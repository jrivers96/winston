#!/usr/bin/env bash
# Build + deploy Winston live-smoke Cloud Run Job in Supercalc project (adept-snow).
set -euo pipefail

: "${CLOUDSDK_PYTHON:=/Users/jonathanrivers/anaconda3/envs/py3.11/bin/python}"
export CLOUDSDK_PYTHON

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PROJECT="${SUPERCALC_GCP_PROJECT:-adept-snow-481601-c6}"
REGION="${SUPERCALC_REGION:-us-central1}"
JOB="${SUPERCALC_LIVE_SMOKE_JOB:-winston-live-smoke}"
IMAGE="gcr.io/${PROJECT}/winston-live-smoke:latest"
INSTANCE="${SUPERCALC_SQL_INSTANCE:-adept-snow-481601-c6:us-central1:polymarket-gvf-db-small}"
CONNECTOR="${SUPERCALC_VPC_CONNECTOR:-polymarket-gvf-connector}"

echo "==> Cloud Build $IMAGE"
gcloud builds submit \
  --project="$PROJECT" \
  --config=ops/winston-ops/cloudrun/cloudbuild.live-smoke.yaml \
  .

echo "==> Create/update Cloud Run job $JOB"
if gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" \
    --project="$PROJECT" \
    --region="$REGION" \
    --image="$IMAGE" \
    --vpc-connector="$CONNECTOR" \
    --vpc-egress=private-ranges-only \
    --set-cloudsql-instances="$INSTANCE" \
    --set-secrets=WINSTON_SUPERCALC_PG_PASSWORD=winston-readonly-password:latest \
    --set-env-vars=WINSTON_OFFLINE_MODE=false,WINSTON_LIVE_SMOKE=1,WINSTON_GCP_PROJECT="$PROJECT" \
    --max-retries=0 \
    --task-timeout=180
else
  gcloud run jobs create "$JOB" \
    --project="$PROJECT" \
    --region="$REGION" \
    --image="$IMAGE" \
    --vpc-connector="$CONNECTOR" \
    --vpc-egress=private-ranges-only \
    --set-cloudsql-instances="$INSTANCE" \
    --set-secrets=WINSTON_SUPERCALC_PG_PASSWORD=winston-readonly-password:latest \
    --set-env-vars=WINSTON_OFFLINE_MODE=false,WINSTON_LIVE_SMOKE=1,WINSTON_GCP_PROJECT="$PROJECT" \
    --max-retries=0 \
    --task-timeout=180
fi

echo "==> Execute once"
gcloud run jobs execute "$JOB" --project="$PROJECT" --region="$REGION" --wait

echo "Done. Inspect logs for capability_label=live-verified."

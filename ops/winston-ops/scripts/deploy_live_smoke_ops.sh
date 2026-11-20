#!/usr/bin/env bash
# Build + deploy Winston live-smoke in winston-ops via Cloud SQL PSC endpoint.
set -euo pipefail

: "${CLOUDSDK_PYTHON:=/Users/jonathanrivers/anaconda3/envs/py3.11/bin/python}"
export CLOUDSDK_PYTHON
export CLOUDSDK_CORE_DISABLE_PROMPTS=1

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

PROJECT="${WINSTON_OPS_PROJECT:-winston-ops-sc}"
REGION="${WINSTON_OPS_REGION:-us-central1}"
JOB="${WINSTON_OPS_LIVE_SMOKE_JOB:-winston-staging-live-smoke}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/winston/winston-live-smoke:latest"
CONNECTOR="${WINSTON_VPC_CONNECTOR:-winston-stg-conn}"
SA="${WINSTON_NIGHTLY_SA:-winston-nightly@${PROJECT}.iam.gserviceaccount.com}"
# PSC auto-connection IP into winston-staging-vpc (from Supercalc Cloud SQL)
PSC_HOST="${SUPERCALC_PSC_HOST:-10.20.0.3}"
SUPERCALC_INSTANCE="${SUPERCALC_SQL_INSTANCE:-adept-snow-481601-c6:us-central1:polymarket-gvf-db-small}"

echo "==> Resolve PSC endpoint if needed"
if [[ -z "${SUPERCALC_PSC_HOST:-}" ]] || [[ "$PSC_HOST" == "10.20.0.3" ]]; then
  RESOLVED=$(gcloud sql instances describe polymarket-gvf-db-small \
    --project=adept-snow-481601-c6 \
    --format="value(settings.ipConfiguration.pscConfig.pscAutoConnections[0].ipAddress)" 2>/dev/null || true)
  if [[ -n "$RESOLVED" && "$RESOLVED" != "NONE" ]]; then
    PSC_HOST="$RESOLVED"
  fi
fi
echo "    PSC host=$PSC_HOST"

echo "==> Ensure Supercalc password secret accessible in winston-ops"
# Copy from adept-snow if winston-ops secret has no version
if ! gcloud secrets versions access latest \
  --secret=winston-staging-supercalc-pg-password --project="$PROJECT" >/dev/null 2>&1; then
  echo "    Seeding winston-staging-supercalc-pg-password from adept-snow"
  gcloud secrets versions access latest \
    --secret=winston-readonly-password \
    --project=adept-snow-481601-c6 \
    | gcloud secrets versions add winston-staging-supercalc-pg-password \
      --project="$PROJECT" \
      --data-file=-
fi

gcloud secrets add-iam-policy-binding winston-staging-supercalc-pg-password \
  --project="$PROJECT" \
  --member="serviceAccount:${SA}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

# cloudsql.client on producer still helps Auth Proxy / admin APIs; TCP to PSC IP is enough for psycopg
gcloud projects add-iam-policy-binding adept-snow-481601-c6 \
  --member="serviceAccount:${SA}" \
  --role="roles/cloudsql.client" >/dev/null 2>&1 || true

echo "==> Write PSC profile for image build"
PROFILE_OUT="$ROOT/ops/winston-ops/cloudrun/supercalc_live_psc.profile.yaml"
sed -e "s|host: \"/cloudsql/.*\"|host: \"${PSC_HOST}\"|" \
    -e 's|sslmode: "disable"|sslmode: "require"|' \
    "$ROOT/ops/winston-ops/cloudrun/supercalc_live.profile.yaml" \
  > "$PROFILE_OUT"

echo "==> Cloud Build $IMAGE"
cat > /tmp/cloudbuild.live-smoke-ops.yaml <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args:
      - build
      - -f
      - ops/winston-ops/cloudrun/Dockerfile.live-smoke-ops
      - -t
      - ${IMAGE}
      - .
images:
  - ${IMAGE}
timeout: 1200s
EOF

gcloud builds submit \
  --project="$PROJECT" \
  --config=/tmp/cloudbuild.live-smoke-ops.yaml \
  .

echo "==> Create/update Cloud Run job $JOB"
COMMON_ARGS=(
  --project="$PROJECT"
  --region="$REGION"
  --image="$IMAGE"
  --service-account="$SA"
  --vpc-connector="$CONNECTOR"
  --vpc-egress=private-ranges-only
  --set-secrets=WINSTON_SUPERCALC_PG_PASSWORD=winston-staging-supercalc-pg-password:latest
  --set-env-vars=WINSTON_OFFLINE_MODE=false,WINSTON_LIVE_SMOKE=1,WINSTON_GCP_PROJECT="$PROJECT",SUPERCALC_PSC_HOST="$PSC_HOST"
  --max-retries=0
  --task-timeout=180
  --memory=1Gi
)

if gcloud run jobs describe "$JOB" --project="$PROJECT" --region="$REGION" >/dev/null 2>&1; then
  gcloud run jobs update "$JOB" "${COMMON_ARGS[@]}"
else
  gcloud run jobs create "$JOB" "${COMMON_ARGS[@]}"
fi

echo "==> Execute once"
gcloud run jobs execute "$JOB" --project="$PROJECT" --region="$REGION" --wait

echo "Done. PSC live-smoke via $PSC_HOST (instance $SUPERCALC_INSTANCE)."

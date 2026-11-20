#!/usr/bin/env bash
# Verify winston_readonly can SELECT Supercalc mapped tables.
# Runs in adept-snow (private Cloud SQL + polymarket-gvf-connector).
# Auth Proxy from a laptop cannot reach private-IP-only Cloud SQL without a VPC path.
set -euo pipefail

: "${CLOUDSDK_PYTHON:=/Users/jonathanrivers/anaconda3/envs/py3.11/bin/python}"
export CLOUDSDK_PYTHON

PROJECT="${SUPERCALC_GCP_PROJECT:-adept-snow-481601-c6}"
REGION="${SUPERCALC_REGION:-us-central1}"
JOB="${SUPERCALC_VERIFY_JOB:-winston-verify-readonly}"

echo "Executing $JOB in $PROJECT ($REGION)..."
gcloud run jobs execute "$JOB" \
  --project="$PROJECT" \
  --region="$REGION" \
  --wait

echo "OK — see Cloud Run execution logs for row counts."
echo "Note: live-smoke that needs Supercalc SQL should run in $PROJECT (or use PSC),"
echo "      not from winston-ops-sc alone — Cloud SQL private IP is not transitive across VPC peers."

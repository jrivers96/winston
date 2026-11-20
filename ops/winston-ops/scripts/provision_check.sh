#!/usr/bin/env bash
# Validate the winston-ops Terraform skeleton without applying.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TF_DIR="$ROOT/ops/winston-ops/terraform"
cd "$TF_DIR"

echo "==> winston-ops provision check (no apply)"

missing=0

require_file() {
  if [[ ! -f "$1" ]]; then
    echo "MISSING: $1"
    missing=1
  else
    echo "OK: $1"
  fi
}

require_file "main.tf"
require_file "variables.tf"
require_file "apis.tf"
require_file "network.tf"
require_file "sql.tf"
require_file "secrets.tf"
require_file "storage.tf"
require_file "iam.tf"
require_file "scheduler.tf"
require_file "outputs.tf"
require_file "terraform.tfvars.example"

if [[ ! -f terraform.tfvars ]]; then
  echo "NOTE: terraform.tfvars not present — copy from terraform.tfvars.example when ready"
else
  echo "OK: terraform.tfvars present"
  if grep -Eq '^[[:space:]]*enable_resources[[:space:]]*=[[:space:]]*true' terraform.tfvars; then
    echo "WARN: enable_resources=true — plan/apply will create billable resources"
  else
    echo "OK: enable_resources is not true (safe default)"
  fi
fi

if command -v terraform >/dev/null 2>&1; then
  echo "==> terraform fmt -check"
  terraform fmt -check -recursive
  echo "==> terraform init -backend=false"
  terraform init -backend=false -input=false >/tmp/winston-ops-tf-init.log
  echo "==> terraform validate"
  # validate needs a project_id even when resources are disabled
  if [[ -f terraform.tfvars ]]; then
    terraform validate
  else
    terraform validate -var="project_id=winston-ops-validate-only"
  fi
  echo "OK: terraform validate"
else
  echo "NOTE: terraform CLI not installed — skipped fmt/init/validate"
fi

if [[ "$missing" -ne 0 ]]; then
  echo "FAIL: skeleton files missing"
  exit 1
fi

echo
echo "Provision check passed."
echo "Next:"
echo "  1. Create dedicated GCP project (not Supercalc production)"
echo "  2. cp terraform.tfvars.example terraform.tfvars  # set real project_id"
echo "  3. Set enable_resources=true only when ready to create resources"
echo "  4. terraform plan && terraform apply   # explicit approval required"
echo "  5. Fill profiles/supercalc_live.yaml with real read-only mappings before live smoke"

output "project_id" {
  value       = var.project_id
  description = "Winston ops GCP project"
}

output "region" {
  value       = var.region
  description = "Primary region"
}

output "enable_resources" {
  value       = var.enable_resources
  description = "Whether billable resources would be created"
}

output "reports_bucket" {
  value       = var.enable_resources ? google_storage_bucket.reports[0].name : local.reports_bucket
  description = "Nightly reports bucket name (created only when enable_resources=true)"
}

output "sql_connection_name" {
  value       = var.enable_resources ? google_sql_database_instance.winston[0].connection_name : null
  description = "Cloud SQL connection name for Winston staging DB"
}

output "nightly_service_account" {
  value       = var.enable_resources ? google_service_account.nightly[0].email : null
  description = "Service account for nightly / staging maintain"
}

output "live_smoke_secret_ids" {
  value = var.enable_resources ? [
    for s in google_secret_manager_secret.live_smoke : s.secret_id
  ] : local.live_smoke_secret_ids
  description = "Empty Secret Manager shells for future live-smoke credentials"
}

output "next_steps" {
  value = compact([
    var.enable_resources ? null : "Set enable_resources=true in terraform.tfvars after project/billing/APIs are ready",
    "Copy terraform.tfvars.example → terraform.tfvars and set project_id",
    "Run: ./ops/winston-ops/scripts/provision_check.sh",
    "Apply only with explicit approval: terraform apply",
    "Fill profiles/supercalc_live.yaml with real read-only mappings before live smoke",
  ])
}

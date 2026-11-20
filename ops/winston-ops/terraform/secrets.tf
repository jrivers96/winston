# Empty Secret Manager shells for future opt-in live smoke.
# Operators add versions manually — Terraform never stores Supercalc credentials.

locals {
  live_smoke_secret_ids = var.create_live_smoke_secret_shells ? [
    # Supercalc read-only Postgres (not Winston agent DB)
    "${local.name_prefix}-supercalc-pg-password",
    # Optional Datadog
    "${local.name_prefix}-datadog-api-key",
    "${local.name_prefix}-datadog-app-key",
  ] : []
}

resource "google_secret_manager_secret" "live_smoke" {
  for_each = var.enable_resources ? toset(local.live_smoke_secret_ids) : toset([])

  secret_id = each.value
  project   = var.project_id

  labels = merge(local.labels, {
    purpose = "live-smoke-readonly"
  })

  replication {
    auto {}
  }

  depends_on = [time_sleep.api_propagation]
}

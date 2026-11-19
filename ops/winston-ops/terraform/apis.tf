# Enable required APIs only when resources are enabled.

locals {
  required_apis = [
    "sqladmin.googleapis.com",
    "secretmanager.googleapis.com",
    "storage.googleapis.com",
    "run.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "artifactregistry.googleapis.com",
  ]
}

resource "google_project_service" "required" {
  for_each = var.enable_resources ? toset(local.required_apis) : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

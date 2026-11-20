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
    "compute.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
  ]
}

resource "google_project_service" "required" {
  for_each = var.enable_resources ? toset(local.required_apis) : toset([])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Newly enabled APIs can 403 for a short window; wait before dependent creates.
resource "time_sleep" "api_propagation" {
  count = var.enable_resources ? 1 : 0

  create_duration = "90s"

  triggers = {
    apis = join(",", sort([for s in google_project_service.required : s.id]))
  }

  depends_on = [google_project_service.required]
}

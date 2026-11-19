# Nightly report artifact bucket.

resource "google_storage_bucket" "reports" {
  count = var.enable_resources ? 1 : 0

  name                        = local.reports_bucket
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "Delete"
    }
  }

  labels = local.labels

  depends_on = [google_project_service.required]
}

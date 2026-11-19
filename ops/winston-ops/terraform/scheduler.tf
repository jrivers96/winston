# Cloud Run Job + Scheduler placeholders for offline nightly.
# The job image/command are filled after the first Artifact Registry push.
# Until then, GitHub Actions nightly remains the default runner.

resource "google_artifact_registry_repository" "winston" {
  count = var.enable_resources ? 1 : 0

  location      = var.region
  repository_id = "winston"
  description   = "Winston ops images (nightly / staging maintain)"
  format        = "DOCKER"
  project       = var.project_id
  labels        = local.labels

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_job" "nightly" {
  count = var.enable_resources ? 1 : 0

  name     = "${local.name_prefix}-nightly"
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.nightly[0].email

      containers {
        # Replace after first image push:
        # ${var.region}-docker.pkg.dev/${var.project_id}/winston/winston-ops:nightly
        image = "us-docker.pkg.dev/cloudrun/container/hello"

        env {
          name  = "WINSTON_OFFLINE_MODE"
          value = "true"
        }
        env {
          name  = "WINSTON_NIGHTLY_OUT"
          value = "/tmp/nightly"
        }

        # DATABASE_URL injected from Secret Manager when Cloud SQL is used
        # for maintain --persist (offline replay does not require it).
      }

      timeout = "1800s"
    }
  }

  lifecycle {
    ignore_changes = [
      # Operators update the image after the first registry push.
      template[0].template[0].containers[0].image,
    ]
  }

  depends_on = [
    google_project_service.required,
    google_artifact_registry_repository.winston,
  ]
}

resource "google_cloud_scheduler_job" "nightly" {
  count = var.enable_resources ? 1 : 0

  name        = "${local.name_prefix}-nightly"
  description = "Trigger Winston offline nightly (fixture + maintain --no-persist)"
  schedule    = var.nightly_schedule
  time_zone   = "UTC"
  region      = var.region
  project     = var.project_id

  http_target {
    http_method = "POST"
    uri = format(
      "https://%s-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/%s/jobs/%s:run",
      var.region,
      var.project_id,
      google_cloud_run_v2_job.nightly[0].name,
    )

    oauth_token {
      service_account_email = google_service_account.nightly[0].email
    }
  }

  depends_on = [google_cloud_run_v2_job.nightly]
}

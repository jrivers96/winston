# Service account for offline nightly + staging maintain (no Supercalc mutate rights).

resource "google_service_account" "nightly" {
  count = var.enable_resources ? 1 : 0

  account_id   = "winston-nightly"
  display_name = "Winston offline nightly / staging maintain"
  project      = var.project_id
}

resource "google_storage_bucket_iam_member" "nightly_reports_writer" {
  count = var.enable_resources ? 1 : 0

  bucket = google_storage_bucket.reports[0].name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.nightly[0].email}"
}

resource "google_secret_manager_secret_iam_member" "nightly_database_url" {
  count = var.enable_resources ? 1 : 0

  secret_id = google_secret_manager_secret.database_url[0].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.nightly[0].email}"
  project   = var.project_id
}

resource "google_project_iam_member" "nightly_cloudsql_client" {
  count = var.enable_resources ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.nightly[0].email}"
}

# Live-smoke secret access is intentionally NOT granted by default.
# Grant roles/secretmanager.secretAccessor on live_smoke secrets only when
# a read-only live profile is filled and WINSTON_LIVE_SMOKE is approved.

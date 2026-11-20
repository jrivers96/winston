# Cloud SQL Postgres for staging Winston agent state (issues/obligations).

resource "random_password" "sql_app" {
  count   = var.enable_resources ? 1 : 0
  length  = 32
  special = false
}

resource "google_sql_database_instance" "winston" {
  count = var.enable_resources ? 1 : 0

  name             = "${local.name_prefix}-pg"
  database_version = "POSTGRES_16"
  region           = var.region
  project          = var.project_id

  settings {
    # ENTERPRISE (not PLUS) so db-f1-micro remains valid for cheap staging
    edition           = "ENTERPRISE"
    tier              = var.sql_tier
    availability_type = "ZONAL"
    disk_size         = var.sql_disk_gb
    disk_type         = "PD_SSD"

    ip_configuration {
      # Org policy sql.restrictPublicIp — private IP only
      ipv4_enabled                                  = false
      private_network                               = google_compute_network.winston[0].id
      enable_private_path_for_google_cloud_services = true
    }

    backup_configuration {
      enabled                        = true
      start_time                     = "07:00"
      point_in_time_recovery_enabled = false
    }

    user_labels = local.labels
  }

  deletion_protection = true

  depends_on = [
    time_sleep.api_propagation,
    google_service_networking_connection.sql_private,
  ]
}

resource "google_sql_database" "winston" {
  count = var.enable_resources ? 1 : 0

  name     = "winston"
  instance = google_sql_database_instance.winston[0].name
  project  = var.project_id
}

resource "google_sql_user" "winston_app" {
  count = var.enable_resources ? 1 : 0

  name     = "winston_app"
  instance = google_sql_database_instance.winston[0].name
  project  = var.project_id
  password = random_password.sql_app[0].result
}

resource "google_secret_manager_secret" "database_url" {
  count = var.enable_resources ? 1 : 0

  secret_id = "${local.name_prefix}-database-url"
  project   = var.project_id

  labels = local.labels

  replication {
    auto {}
  }

  depends_on = [time_sleep.api_propagation]
}

resource "google_secret_manager_secret_version" "database_url" {
  count = var.enable_resources ? 1 : 0

  secret = google_secret_manager_secret.database_url[0].id
  secret_data = format(
    "postgresql+psycopg://%s:%s@/%s?host=/cloudsql/%s",
    google_sql_user.winston_app[0].name,
    random_password.sql_app[0].result,
    google_sql_database.winston[0].name,
    google_sql_database_instance.winston[0].connection_name,
  )
}

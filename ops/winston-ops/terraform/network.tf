# Private VPC for Cloud SQL (org policy: sql.restrictPublicIp).

resource "google_compute_network" "winston" {
  count = var.enable_resources ? 1 : 0

  name                    = "${local.name_prefix}-vpc"
  auto_create_subnetworks = false
  project                 = var.project_id

  depends_on = [time_sleep.api_propagation]
}

resource "google_compute_subnetwork" "winston" {
  count = var.enable_resources ? 1 : 0

  name          = "${local.name_prefix}-subnet"
  ip_cidr_range = "10.20.0.0/24"
  region        = var.region
  network       = google_compute_network.winston[0].id
  project       = var.project_id

  private_ip_google_access = true
}

resource "google_compute_global_address" "sql_private" {
  count = var.enable_resources ? 1 : 0

  name          = "${local.name_prefix}-sql-private"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.winston[0].id
  project       = var.project_id
}

resource "google_service_networking_connection" "sql_private" {
  count = var.enable_resources ? 1 : 0

  network                 = google_compute_network.winston[0].id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.sql_private[0].name]

  depends_on = [time_sleep.api_propagation]
}

# Cloud Run → private Cloud SQL
resource "google_vpc_access_connector" "winston" {
  count = var.enable_resources ? 1 : 0

  name          = "winston-stg-conn"
  region        = var.region
  project       = var.project_id
  network       = google_compute_network.winston[0].name
  ip_cidr_range = "10.20.1.0/28"

  min_instances = 2
  max_instances = 3

  depends_on = [time_sleep.api_propagation]
}

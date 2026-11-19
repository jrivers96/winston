# Skeleton only — do not apply until project IDs and APIs are confirmed.
# Intended project: winston-ops (separate from Supercalc production).

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP project ID for Winston ops (e.g. winston-ops)"
}

variable "region" {
  type    = string
  default = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Example placeholders (commented until ready):
#
# resource "google_sql_database_instance" "winston" {
#   name             = "winston-staging"
#   database_version = "POSTGRES_16"
#   region           = var.region
#   settings {
#     tier = "db-f1-micro"
#   }
# }
#
# resource "google_service_account" "nightly" {
#   account_id   = "winston-nightly"
#   display_name = "Winston nightly replay"
# }
#
# resource "google_storage_bucket" "reports" {
#   name     = "${var.project_id}-winston-nightly-reports"
#   location = var.region
# }

output "project_id" {
  value = var.project_id
}

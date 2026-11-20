# winston-ops Terraform root
# Skeleton only — default enable_resources=false creates nothing billable.
# Intended project: winston-ops (separate from Supercalc production).

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5"
    }
    time = {
      source  = "hashicorp/time"
      version = ">= 0.9"
    }
  }

  # Backend intentionally unset. Add a remote backend in the winston-ops
  # project after the state bucket exists (do not store state in Supercalc).
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  name_prefix = "winston-${var.environment}"
  reports_bucket = (
    var.reports_bucket_name != ""
    ? var.reports_bucket_name
    : "${var.project_id}-winston-nightly-reports"
  )
  labels = {
    app         = "winston"
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "ops-continual-testing"
  }
}

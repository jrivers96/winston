# Skeleton variables — fill terraform.tfvars from the example before plan/apply.
# Do not invent Supercalc production names here; Winston ops only.

variable "project_id" {
  type        = string
  description = "GCP project ID for Winston ops (dedicated; not Supercalc production)"
}

variable "region" {
  type        = string
  description = "Primary region for Cloud SQL, buckets, and jobs"
  default     = "us-central1"
}

variable "environment" {
  type        = string
  description = "Staging environment label"
  default     = "staging"
}

variable "enable_resources" {
  type        = bool
  description = <<-EOT
    When false (default), Terraform configures the provider and validates
    inputs but creates no billable resources. Set true only after the
    winston-ops project exists, billing is linked, and APIs are approved.
  EOT
  default     = false
}

variable "sql_tier" {
  type        = string
  description = "Cloud SQL machine tier for staging Winston state"
  default     = "db-f1-micro"
}

variable "sql_disk_gb" {
  type        = number
  description = "Cloud SQL disk size in GB"
  default     = 10
}

variable "reports_bucket_name" {
  type        = string
  description = "GCS bucket for nightly report artifacts (must be globally unique)"
  default     = ""
}

variable "nightly_schedule" {
  type        = string
  description = "Cron schedule for offline nightly (UTC)"
  default     = "0 8 * * *"
}

variable "create_live_smoke_secret_shells" {
  type        = bool
  description = <<-EOT
    Create empty Secret Manager secret shells for future live-smoke credentials.
    Secret values are never set by Terraform; operators add versions manually.
  EOT
  default     = true
}

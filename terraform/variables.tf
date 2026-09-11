variable "project_id" {
  description = "Your GCP project ID (from the console, e.g. rootcause-agent-123456)"
  type        = string
}

variable "region" {
  description = "GCP region for Cloud Scheduler jobs and Cloud Run"
  type        = string
  default     = "us-central1"
}

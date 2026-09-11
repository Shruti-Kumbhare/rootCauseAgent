# Cloud Scheduler jobs, targeting httpbin.org test endpoints so we get
# REAL Cloud Scheduler execution logs and REAL failure HTTP codes, without
# needing to deploy a Cloud Function as the target. Swap these URIs for
# your own service endpoints whenever you're ready to move past testing.
#
# httpbin.org/status/<code> always returns that exact status code -- handy
# for deliberately simulating each failure type on demand.

# Healthy job -- should succeed every run. Useful as a control/baseline
# so your report can show "not everything is broken."
resource "google_cloud_scheduler_job" "health_check_ping" {
  name        = "health-check-ping"
  description = "Pings a healthy endpoint every 15 minutes. Expected to always succeed."
  schedule    = "*/15 * * * *"
  time_zone   = "UTC"
  region      = var.region

  http_target {
    http_method = "GET"
    uri         = "https://httpbin.org/status/200"
  }

  retry_config {
    retry_count = 1
  }

  depends_on = [google_project_service.cloudscheduler]
}

# Simulates an auth failure (401) -- the target rejects the request as
# unauthenticated, mirroring nightly-billing-sync's failure mode.
resource "google_cloud_scheduler_job" "billing_sync" {
  name        = "nightly-billing-sync"
  description = "Simulates a billing sync job that fails with 401 (auth failure)."
  schedule    = "0 2 * * *"
  time_zone   = "UTC"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "https://httpbin.org/status/401"
  }

  retry_config {
    retry_count = 1
  }

  depends_on = [google_project_service.cloudscheduler]
}

# Simulates a target-side 500 error, mirroring inventory-refresh-hourly.
resource "google_cloud_scheduler_job" "inventory_refresh" {
  name        = "inventory-refresh-hourly"
  description = "Simulates an inventory refresh job that fails with 500 (endpoint error)."
  schedule    = "0 * * * *"
  time_zone   = "UTC"
  region      = var.region

  http_target {
    http_method = "GET"
    uri         = "https://httpbin.org/status/500"
  }

  retry_config {
    retry_count = 1
  }

  depends_on = [google_project_service.cloudscheduler]
}

# Simulates a misconfigured endpoint (404), mirroring weekly-cleanup-job.
resource "google_cloud_scheduler_job" "weekly_cleanup" {
  name        = "weekly-cleanup-job"
  description = "Simulates a cleanup job hitting a URL that no longer exists (404)."
  schedule    = "0 3 * * 0"
  time_zone   = "UTC"
  region      = var.region

  http_target {
    http_method = "GET"
    uri         = "https://httpbin.org/status/404"
  }

  retry_config {
    retry_count = 1
  }

  depends_on = [google_project_service.cloudscheduler]
}

# Simulates a slow endpoint that exceeds Cloud Scheduler's attempt
# deadline, producing a real timeout/504-style failure, mirroring
# daily-report-generator.
resource "google_cloud_scheduler_job" "daily_report_generator" {
  name        = "daily-report-generator"
  description = "Simulates a report job whose target is too slow, causing a timeout."
  schedule    = "0 6 * * *"
  time_zone   = "UTC"
  region      = var.region

  http_target {
    http_method = "GET"
    # httpbin.org/delay/N waits N seconds before responding.
    # attempt_deadline below is shorter than this, forcing a timeout.
    uri = "https://httpbin.org/delay/35"
  }

  attempt_deadline = "30s"

  retry_config {
    retry_count = 1
  }

  depends_on = [google_project_service.cloudscheduler]
}

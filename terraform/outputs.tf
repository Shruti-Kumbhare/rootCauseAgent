output "scheduler_job_names" {
  description = "Names of all Cloud Scheduler jobs created"
  value = [
    google_cloud_scheduler_job.health_check_ping.name,
    google_cloud_scheduler_job.billing_sync.name,
    google_cloud_scheduler_job.inventory_refresh.name,
    google_cloud_scheduler_job.weekly_cleanup.name,
    google_cloud_scheduler_job.daily_report_generator.name,
  ]
}

output "project_id" {
  value = var.project_id
}

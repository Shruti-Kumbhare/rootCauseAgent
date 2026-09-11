# Terraform — GCP infra for RootCause Agent (Phase 1)

Manages:
- Enabling required GCP APIs (Cloud Scheduler, Cloud Logging, Cloud Run)
- 5 Cloud Scheduler jobs, targeting httpbin.org test endpoints so you get
  **real** Cloud Scheduler execution logs and real failure codes without
  needing to deploy a Cloud Function first. One job (`health-check-ping`)
  is a healthy control; the other four each simulate one of the failure
  scenarios your mock data was already modeling (auth failure, timeout,
  endpoint error, config/404 issue).

## Setup

1. Make sure you've already run `gcloud init` and
   `gcloud auth application-default login` (see the account setup steps).
2. `cp terraform.tfvars.example terraform.tfvars` and fill in your real
   `project_id` (from the GCP console).
3. `terraform init`
4. `terraform plan` — review what it's about to create
5. `terraform apply` — type `yes` to confirm

## Verify

- GCP Console → Cloud Scheduler → you should see 5 jobs listed
- Wait for a run (or click "Force run" on a job in the console to trigger
  it immediately instead of waiting for its schedule)
- GCP Console → Logging → Logs Explorer → filter by
  `resource.type="cloud_scheduler_job"` → you should see real execution
  logs, including failures for the 4 non-healthy jobs

## Next step

Once real failures are landing in Cloud Logging, `mock_gcp_logs.py` in
the main project gets replaced with a real query against Cloud Logging
using the `google-cloud-logging` Python client — same return shape,
nothing else in the pipeline changes.

## Teardown

`terraform destroy` when you're done experimenting, to avoid any jobs
running indefinitely (they're cheap/free-tier, but good practice).

## Swapping in your own endpoints later

Once you have a real target (e.g. a Cloud Function), just change the
`uri` in `scheduler_jobs.tf` for the relevant job — everything else
(schedule, retry config) stays the same.

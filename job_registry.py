"""
Job registry: describes what each Cloud Scheduler job actually does.

This is the missing context the LLM needs. Without it, the agent only sees
a job name + error message and has to guess what the job is for. With it,
diagnosis and suggested fixes can be grounded in what the job is actually
supposed to do -- e.g. knowing that 'nightly-billing-sync' PUSHES data to
an external billing API (so a 401 likely means an expired service-account
token) vs. just seeing "401 Unauthorized" in isolation.

In Phase 1 (real GCP), this would move to a config file (YAML/JSON) or a
small Firestore/BigQuery table so it's editable without a code change --
kept as a plain dict here since it's still prototype stage.
"""

JOB_REGISTRY: dict[str, dict] = {
    "nightly-billing-sync": {
        "description": (
            "Runs nightly at 2 AM. Pulls billing records from the internal "
            "billing DB and pushes them to an external billing API "
            "(target-api.example.com) via a service-account-authenticated "
            "POST request."
        ),
        "expected_input": "Billing DB records for the previous 24h",
        "expected_output": "200 OK from target-api.example.com per batch pushed",
        "owner_team": "Billing",
        "criticality": "high",
    },
    "daily-report-generator": {
        "description": (
            "Runs daily at 6 AM. Aggregates the previous day's metrics "
            "and generates a summary report, then emails it to stakeholders "
            "via a Cloud Function endpoint."
        ),
        "expected_input": "Aggregated metrics from the previous day",
        "expected_output": "Generated report + confirmation email sent",
        "owner_team": "Analytics",
        "criticality": "medium",
    },
    "inventory-refresh-hourly": {
        "description": (
            "Runs hourly. Refreshes the inventory cache by calling a "
            "Cloud Function that reads current stock levels per SKU and "
            "writes them to the cache layer."
        ),
        "expected_input": "Current SKU list + stock levels",
        "expected_output": "Updated inventory cache entries",
        "owner_team": "Inventory",
        "criticality": "high",
    },
    "weekly-cleanup-job": {
        "description": (
            "Runs weekly on Sundays. Calls a cleanup endpoint to remove "
            "stale temp files and expired session data."
        ),
        "expected_input": "None -- runs on a fixed schedule with no payload",
        "expected_output": "Deletion confirmation + count of items removed",
        "owner_team": "Platform",
        "criticality": "low",
    },
    "health-check-ping": {
        "description": "Runs every 5 minutes. Pings a health endpoint to confirm service liveness.",
        "expected_input": "None",
        "expected_output": "200 OK",
        "owner_team": "Platform",
        "criticality": "medium",
    },
    "cache-warmup": {
        "description": "Runs every 15 minutes. Pre-warms the application cache after deploys.",
        "expected_input": "None",
        "expected_output": "200 OK + cache populated",
        "owner_team": "Platform",
        "criticality": "low",
    },
    "log-rotation": {
        "description": "Runs daily at midnight. Rotates and archives application logs.",
        "expected_input": "None",
        "expected_output": "200 OK + archived log confirmation",
        "owner_team": "Platform",
        "criticality": "low",
    },
}


def get_job_context(job_name: str) -> dict:
    """
    Returns job metadata for a given job name, or a generic fallback if
    the job isn't in the registry (e.g. a new job that hasn't been
    documented yet -- the agent should still work, just with less context).
    """
    return JOB_REGISTRY.get(
        job_name,
        {
            "description": "No description on file for this job.",
            "expected_input": "Unknown",
            "expected_output": "Unknown",
            "owner_team": "Unknown",
            "criticality": "Unknown",
        },
    )

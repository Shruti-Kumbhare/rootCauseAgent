"""
Mock GCP Cloud Scheduler + Cloud Logging data.

This module simulates the shape of what google-cloud-logging's client
returns when you query for Cloud Scheduler job execution logs. In Phase 1,
this file gets replaced by a real query against Cloud Logging -- the
function signature (fetch_failed_job_logs() -> list[dict]) stays the same,
so nothing downstream (the LangGraph nodes) needs to change.
"""

from datetime import datetime, timedelta
import random

# Realistic failure patterns a Cloud Scheduler job can hit
FAILURE_SCENARIOS = [
    {
        "job_name": "nightly-billing-sync",
        "status": "FAILED",
        "http_status": 401,
        "error_message": "Request had invalid authentication credentials. "
                          "Expected OAuth 2.0 access token, login cookie or "
                          "other valid authentication credential.",
    },
    {
        "job_name": "daily-report-generator",
        "status": "FAILED",
        "http_status": 504,
        "error_message": "The request timed out after 30000ms waiting for "
                          "a response from the target endpoint.",
    },
    {
        "job_name": "inventory-refresh-hourly",
        "status": "FAILED",
        "http_status": 500,
        "error_message": "Internal Server Error: target Cloud Function "
                          "threw an unhandled exception: KeyError: 'sku_id'",
    },
    {
        "job_name": "weekly-cleanup-job",
        "status": "FAILED",
        "http_status": 404,
        "error_message": "The requested URL /api/v2/cleanup was not found "
                          "on this server. Target endpoint may have been "
                          "renamed or removed.",
    },
    {
        "job_name": "nightly-billing-sync",
        "status": "FAILED",
        "http_status": 429,
        "error_message": "Quota exceeded for quota metric 'Requests' and "
                          "limit 'Requests per minute' of service "
                          "target-api.example.com.",
    },
]

SUCCESS_JOB_NAMES = ["health-check-ping", "cache-warmup", "log-rotation"]


def fetch_failed_job_logs(hours: int = 24) -> list[dict]:
    """
    Simulates querying Cloud Logging for FAILED Cloud Scheduler job runs
    in the last `hours`. Real version (Phase 1) will call:

        from google.cloud import logging_v2
        client = logging_v2.Client()
        client.list_entries(filter_=...)

    and reshape entries into this same list[dict] format.
    """
    now = datetime.utcnow()
    logs = []
    for scenario in FAILURE_SCENARIOS:
        entry = dict(scenario)
        entry["timestamp"] = (
            now - timedelta(minutes=random.randint(1, hours * 60))
        ).isoformat() + "Z"
        entry["log_name"] = f"projects/mock-project/logs/cloudscheduler.googleapis.com%2Fexecutions"
        logs.append(entry)
    # newest first, like Cloud Logging's default ordering
    logs.sort(key=lambda e: e["timestamp"], reverse=True)
    return logs

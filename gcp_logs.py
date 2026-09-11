"""
Real Cloud Logging query for failed Cloud Scheduler job runs.

Return shape matches mock_gcp_logs.fetch_failed_job_logs() exactly, so
graph.py only needs a one-line import change to switch from mock to real
data -- nothing else in the pipeline changes.

Real payload shape (confirmed by inspecting actual logs via
debug_scheduler_logs.py):

  Success (AttemptFinished, severity=INFO):
    {'debugInfo': 'URL_CRAWLED. Original HTTP response code number = 200',
     '@type': '...AttemptFinished', 'jobName': '...', 'url': '...',
     'targetType': 'HTTP'}
    (no top-level 'status' field on success)

  Failure (AttemptFinished, severity=ERROR):
    {'debugInfo': 'URL_ERROR-ERROR_AUTHENTICATION. Original HTTP response '
                  'code number = 401',
     '@type': '...AttemptFinished', 'jobName': '...', 'url': '...',
     'status': 'UNAUTHENTICATED', 'targetType': 'HTTP'}
    ('status' is a gRPC-style status name, present only on failures)
"""

import os
import re
from datetime import datetime, timedelta, timezone

from google.cloud import logging_v2

_HTTP_CODE_PATTERN = re.compile(r"response code number = (\d+)")


def _extract_http_status(debug_info: str) -> int | None:
    match = _HTTP_CODE_PATTERN.search(debug_info or "")
    return int(match.group(1)) if match else None


def fetch_failed_job_logs(hours: int = 24) -> list[dict]:
    """
    Queries Cloud Logging for FAILED Cloud Scheduler job attempts in the
    last `hours`. Only AttemptFinished entries are considered -- 
    AttemptStarted entries carry no result info and are skipped.
    """
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "GCP_PROJECT_ID not set. Add it to your .env file "
            "(e.g. GCP_PROJECT_ID=rca-scheduler-monitor)."
        )

    client = logging_v2.Client(project=project_id)
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

    filter_str = (
        'resource.type="cloud_scheduler_job" '
        'AND severity=ERROR '
        f'AND timestamp>="{cutoff}"'
    )

    entries = client.list_entries(filter_=filter_str, order_by=logging_v2.DESCENDING)

    logs = []
    for entry in entries:
        payload = dict(entry.payload or {})

        # Only AttemptFinished entries have a result to analyze.
        if not payload.get("@type", "").endswith("AttemptFinished"):
            continue

        job_name = entry.resource.labels.get("job_id", "unknown-job")
        debug_info = payload.get("debugInfo", "")
        status_name = payload.get("status", "UNKNOWN")
        http_status = _extract_http_status(debug_info)

        logs.append(
            {
                "job_name": job_name,
                "status": "FAILED",
                "http_status": http_status,
                "error_message": f"{status_name}: {debug_info}",
                "timestamp": entry.timestamp.isoformat(),
                "log_name": f"projects/{project_id}/logs/cloudscheduler.googleapis.com%2Fexecutions",
            }
        )

    return logs
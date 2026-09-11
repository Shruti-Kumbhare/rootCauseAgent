# RootCause Agent

A LangGraph-based SRE assistant for diagnosing failed Google Cloud Scheduler jobs.

The system reads job failures, enriches them with job metadata, asks Gemini to classify the likely root cause, pauses for human review when confidence is low, and produces a final failure report with recommended remediation.

## Current architecture

```text
main.py
  -> build_graph()
  -> fetch_logs_node()
  -> analyze_failures_node()
  -> review_low_confidence_node()
  -> propose_actions_node()
  -> approve_actions_node()
  -> execute_actions_node()
  -> generate_report_node()

api.py
  -> FastAPI wrapper for the same graph
  -> /health
  -> /check-failures
  -> /resume
```

## Workflow

```text
fetch_logs -> analyze_failures -> review_low_confidence -> propose_actions
                                  -> approve_actions -> execute_actions -> generate_report
```

### What each stage does

1. `fetch_logs`
   - Pulls failed Cloud Scheduler executions from either mock data or GCP Cloud Logging.
2. `analyze_failures`
   - Sends the failed jobs to Gemini in one batch request.
   - Uses `job_registry.py` to add job-specific context.
3. `review_low_confidence`
   - If a diagnosis is below the confidence threshold, the graph pauses and waits for human review.
4. `propose_actions`
   - Maps each category to a recommended operational action.
5. `approve_actions`
   - Pauses again so a human approves or rejects each action.
6. `execute_actions`
   - Marks the action as executed or skipped for the report.
7. `generate_report`
   - Produces a Markdown report summarizing each job failure, diagnosis, confidence, and action status.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Local entry point for the agent. Runs the LangGraph workflow and handles human interrupts in the terminal. |
| `api.py` | FastAPI layer for remote execution and resume flow. |
| `graph.py` | Main workflow orchestration, state model, and human-in-the-loop checkpoints. |
| `llm_client.py` | Gemini integration and structured result parsing. |
| `job_registry.py` | Business context for each scheduler job so the model can reason accurately. |
| `mock_gcp_logs.py` | Simulated failed Cloud Scheduler logs for local testing without GCP. |
| `gcp_logs.py` | Real Cloud Logging query for production-style log ingestion. |
| `terraform/` | Terraform config for GCP APIs and Cloud Scheduler jobs. |
| `requirements.txt` | Python dependencies. |
| `.env` / `env.example` | Local environment configuration. |

## Supported failure categories

The model is expected to classify failures as one of:

- `auth_failure`
- `timeout`
- `endpoint_error`
- `config_issue`
- `rate_limit`
- `unknown`

## Why job context matters

The agent does not just inspect a raw `401` or `500` error. It also receives job metadata from `job_registry.py`, including:

- job description
- expected input
- expected output
- owner team
- criticality

This helps the LLM infer whether a failure is a permissions issue, a misconfiguration, a slow target, or a rate-limit problem.

## Local development setup

1. Create a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file using the example file:

```bash
copy env.example .env
```

Then set values like:

```env
GEMINI_API_KEY=your_key_here
GCP_PROJECT_ID=rca-scheduler-monitor
```

4. Run the local workflow:

```bash
python main.py
```

If a diagnosis is below the confidence threshold, the app will pause and ask for a human decision. The same is true before an action is executed.

## FastAPI usage

The API layer exposes the same graph over HTTP.

### Health check

```bash
GET /health
```

### Start a run

```bash
POST /check-failures
```

This returns either:

- a completed report, or
- a pending approval response with a `thread_id` and interrupt payload

### Resume after approval

```bash
POST /resume
```

Example payload:

```json
{
  "thread_id": "abc123",
  "resume": {
    "jobA": "approve"
  }
}
```

## GCP integration

The project includes a real Cloud Logging adapter in `gcp_logs.py` that queries failed Cloud Scheduler executions and normalizes them into the same shape as the mock data.

This means the graph logic does not need to change when moving from mock logs to real logs.

## Terraform infrastructure

The `terraform/` folder provisions a real testing environment in GCP:

- enables required APIs
- creates Cloud Scheduler jobs
- simulates failure scenarios with public endpoints
- stores output values for the project and created jobs

### Example usage

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

This creates scheduler jobs such as:

- `health-check-ping`
- `nightly-billing-sync`
- `inventory-refresh-hourly`
- `weekly-cleanup-job`
- `daily-report-generator`

## Current status

This project is an operational prototype for Cloud Scheduler failure analysis with human-in-the-loop safety checks.

The current architecture is:

- local or API-driven workflow orchestration
- Gemini-backed root-cause analysis
- job metadata grounding
- human review for low confidence and risky actions
- optional real GCP log collection
- Terraform-managed infrastructure for testing in Google Cloud

## Future work

1. Replace simulated action execution with real GCP remediation calls.
2. Move the job registry to a persisted source such as YAML, Firestore, or BigQuery.
3. Add persistent checkpoint storage for the LangGraph API.
4. Deploy the API to Cloud Run.
5. Add auth, audit logging, and a production-safe approval model.
6. Add richer retry and fallback logic for quota or model failures.

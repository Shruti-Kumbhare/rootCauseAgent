# Scheduler Failure Monitor — Prototype 

A 3-node LangGraph pipeline that analyzes failed Cloud Scheduler jobs and
produces a root-cause report.

```
fetch_logs -> analyze_failures -> generate_report
```

Currently backed by **mock log data** (`mock_gcp_logs.py`) so it runs with
zero GCP setup. Root cause analysis is real — powered by the Gemini API.

## Setup

1. Get a free Gemini API key: https://aistudio.google.com/apikey (no credit card needed)
2. `cp .env.example .env` and paste your key in
3. `pip install -r requirements.txt`
4. `python main.py`

You'll see each node log its progress, then a Markdown-style report of all
"failed" jobs with root cause, confidence, and a suggested fix.

## What's already verified

- Mock log generator produces realistic failure scenarios (auth, timeout,
  5xx, 404, rate limit)
- LangGraph graph compiles and the `fetch_logs` node runs end-to-end
- Full pipeline (incl. Gemini call) needs your API key to test — do that
  next

## Files

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

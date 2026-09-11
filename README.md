# Scheduler Failure Monitor — Prototype (Phase 2 in your phased plan)

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
| `mock_gcp_logs.py` | Simulates Cloud Logging output. Swap for a real `google-cloud-logging` query in Phase 1 — same return shape, nothing else changes. |
| `llm_client.py` | Swappable LLM wrapper. Only file to touch if you move to Vertex AI or another provider later. |
| `graph.py` | The LangGraph state machine — 3 nodes, shared typed state. |
| `main.py` | Entry point. |

## Next steps (per your phased plan)

1. **Phase 1** — Set up real GCP project (Cloud Scheduler + Cloud Logging),
   replace `mock_gcp_logs.fetch_failed_job_logs()` with a real query
2. **Phase 3** — Wrap `graph.py` in a FastAPI endpoint
3. **Phase 4** — Containerize, deploy to Cloud Run
4. **Phase 5** — Cloud Scheduler triggers your own endpoint on an interval
5. **Phase 6 (optional)** — Add bounded retry loop for low-confidence
   results + separate Resolution Agent

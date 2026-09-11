"""
Thin, swappable LLM client.

The Root Cause Analyzer node calls `analyze_failures_batch()`. Today
that's backed by the Gemini API (AI Studio). If you ever move to Vertex AI
or another provider, you only need to change what's inside this file --
graph.py never needs to know which LLM is behind it.
"""

import os
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from tenacity import retry, stop_after_attempt, wait_exponential

from job_registry import get_job_context


class RootCauseResult(BaseModel):
    job_name: str = Field(description="The job name this diagnosis is for")
    root_cause_category: str = Field(
        description="One of: auth_failure, timeout, endpoint_error, "
        "config_issue, rate_limit, unknown"
    )
    explanation: str = Field(
        description="Plain-language explanation of what went wrong, "
        "referencing what the job is actually supposed to do"
    )
    suggested_fix: str = Field(
        description="Concrete, actionable suggestion to resolve the failure"
    )
    confidence: float = Field(
        description="Confidence in this diagnosis, from 0.0 to 1.0"
    )


class BatchRootCauseResult(BaseModel):
    results: list[RootCauseResult] = Field(
        description="One diagnosis per failed job, in the same order given"
    )


_BATCH_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are an SRE assistant that diagnoses Cloud Scheduler job "
            "failures from their log entries. Each job includes context on "
            "what it's actually supposed to do, its expected input/output, "
            "and which team owns it -- use that context to give a specific, "
            "grounded diagnosis rather than guessing from the error alone. "
            "You'll be given a list of failed jobs. Diagnose each one and "
            "return one result per job, in the same order, including its "
            "job_name. Be specific and concise.",
        ),
        (
            "human",
            "Failed jobs:\n\n{failures_block}",
        ),
    ]
)


def _is_daily_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "PerDay" in msg or "RequestsPerDay" in msg


def get_llm():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY not set. Get a free key at "
            "https://aistudio.google.com/apikey and set it in your .env file."
        )
    model_name = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
    return ChatGoogleGenerativeAI(model=model_name, google_api_key=api_key)


def _format_failure_block(entry: dict) -> str:
    ctx = get_job_context(entry["job_name"])
    return (
        f"- job_name: {entry['job_name']}\n"
        f"  http_status: {entry['http_status']}\n"
        f"  error_message: {entry['error_message']}\n"
        f"  job_description: {ctx['description']}\n"
        f"  expected_input: {ctx['expected_input']}\n"
        f"  expected_output: {ctx['expected_output']}\n"
        f"  owner_team: {ctx['owner_team']}\n"
        f"  criticality: {ctx['criticality']}"
    )


def _should_retry(retry_state) -> bool:
    if not retry_state.outcome or not retry_state.outcome.failed:
        return False  # call succeeded -- never retry a success
    exc = retry_state.outcome.exception()
    return not _is_daily_quota_error(exc)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=10, max=60),
    retry=_should_retry,
    reraise=True,
)
def analyze_failures_batch(logs: list[dict]) -> list[RootCauseResult]:
    """
    Analyzes ALL failed jobs in a single LLM call, instead of one call per
    job -- 1 request per pipeline run instead of N, which matters a lot on
    a tight daily quota. Each job's failure is enriched with its registered
    context (what it does, expected I/O, owning team) before being sent.
    """
    if not logs:
        return []

    failures_block = "\n\n".join(_format_failure_block(e) for e in logs)

    llm = get_llm().with_structured_output(BatchRootCauseResult)
    chain = _BATCH_PROMPT | llm
    try:
        batch_result = chain.invoke({"failures_block": failures_block})
    except Exception as exc:
        if _is_daily_quota_error(exc):
            raise RuntimeError(
                "Gemini free-tier DAILY quota exceeded for this model. "
                "This resets at midnight Pacific Time -- no amount of "
                "retrying will help until then. Try again tomorrow, or "
                "switch GEMINI_MODEL to a different model with its own "
                "separate daily quota (e.g. gemini-3.1-flash-lite)."
            ) from exc
        raise
    return batch_result.results

"""
FastAPI wrapper around the RootCause Agent LangGraph pipeline.

HITL over HTTP: interrupt()/Command(resume=...) needs a thread_id to know
which paused run to resume. Since HTTP is stateless, the client is
responsible for holding onto the thread_id between calls:

    1. POST /check-failures         -> starts a new run
    2. Response is either:
         - {"status": "completed", "report": "..."}
         - {"status": "pending_approval", "thread_id": "...",
            "interrupt_type": "...", "payload": {...}}
    3. If pending_approval, client collects a decision and calls:
         POST /resume  {"thread_id": "...", "resume": {...}}
    4. Repeat step 2/3 until status is "completed" (there are up to two
       pauses per run: low-confidence review, then action approval)

Known limitation: this uses graph.py's MemorySaver checkpointer, which
only persists in-process. On Cloud Run, an instance restart (or a
different instance handling the resume call) loses paused state. Fine
for local Phase 3 development; Phase 4 deployment needs a persistent
checkpointer (e.g. Postgres-backed) before this is safe in production.
"""

import uuid
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langgraph.types import Command

from graph import build_graph

app = FastAPI(title="RootCause Agent API")
graph_app = build_graph()


class ResumeRequest(BaseModel):
    thread_id: str
    resume: dict[str, Any]


class RunResponse(BaseModel):
    status: str  # "completed" | "pending_approval"
    thread_id: str
    report: str | None = None
    interrupt_type: str | None = None
    payload: dict[str, Any] | None = None


def _to_response(thread_id: str, result: dict) -> RunResponse:
    if "__interrupt__" in result:
        interrupt_obj = result["__interrupt__"][0]
        return RunResponse(
            status="pending_approval",
            thread_id=thread_id,
            interrupt_type=interrupt_obj.value["type"],
            payload=interrupt_obj.value,
        )
    return RunResponse(status="completed", thread_id=thread_id, report=result["report"])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check-failures", response_model=RunResponse)
def check_failures():
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    result = graph_app.invoke(
        {
            "raw_logs": [],
            "analyses": [],
            "proposed_actions": [],
            "action_approvals": {},
            "execution_results": [],
            "report": "",
        },
        config=config,
    )
    return _to_response(thread_id, result)


@app.post("/resume", response_model=RunResponse)
def resume(req: ResumeRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    try:
        result = graph_app.invoke(Command(resume=req.resume), config=config)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not resume run: {exc}")
    return _to_response(req.thread_id, result)

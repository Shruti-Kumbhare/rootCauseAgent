"""
LangGraph pipeline for Cloud Scheduler failure monitoring, with two
human-in-the-loop checkpoints:

    fetch_logs -> analyze_failures -> review_low_confidence (HITL #1)
        -> propose_actions -> approve_actions (HITL #2)
        -> execute_actions -> generate_report

HITL #1: any diagnosis below LOW_CONFIDENCE_THRESHOLD pauses for a human
to confirm or correct it before it's treated as final.

HITL #2: before any remediation action is "executed" (simulated here --
in Phase 1 this could hit real GCP APIs), a human must approve it. This
is the safety-gate pattern: the agent proposes, a human decides.

Uses LangGraph's interrupt()/Command(resume=...) mechanism, which requires
a checkpointer (MemorySaver here, for local/in-memory use).
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import interrupt

from gcp_logs import fetch_failed_job_logs
from llm_client import analyze_failures_batch

LOW_CONFIDENCE_THRESHOLD = 0.75

ACTION_MAP = {
    "auth_failure": "Rotate/renew the service account credentials used by this job",
    "timeout": "Increase the job's attempt deadline / timeout configuration",
    "endpoint_error": "Notify the owning team to investigate the target endpoint",
    "config_issue": "Update the job's target URI configuration",
    "rate_limit": "Adjust the job's schedule to reduce request frequency, or request a quota increase",
    "unknown": "Escalate to on-call for manual investigation",
}


class FailureAnalysis(TypedDict):
    job_name: str
    http_status: int
    error_message: str
    timestamp: str
    root_cause_category: str
    explanation: str
    suggested_fix: str
    confidence: float


class ProposedAction(TypedDict):
    job_name: str
    action: str
    category: str


class ExecutionResult(TypedDict):
    job_name: str
    action: str
    status: str  # "executed" | "skipped"


class GraphState(TypedDict):
    raw_logs: list[dict]
    analyses: list[FailureAnalysis]
    proposed_actions: list[ProposedAction]
    action_approvals: dict[str, bool]
    execution_results: list[ExecutionResult]
    report: str


def fetch_logs_node(state: GraphState) -> GraphState:
    logs = fetch_failed_job_logs(hours=24)
    print(f"[fetch_logs] found {len(logs)} failed job runs")
    return {"raw_logs": logs}


def analyze_failures_node(state: GraphState) -> GraphState:
    results = analyze_failures_batch(state["raw_logs"])
    logs_by_name = {e["job_name"]: e for e in state["raw_logs"]}
    analyses: list[FailureAnalysis] = []
    for r in results:
        entry = logs_by_name.get(r.job_name, {})
        analyses.append(
            {
                "job_name": r.job_name,
                "http_status": entry.get("http_status"),
                "error_message": entry.get("error_message"),
                "timestamp": entry.get("timestamp"),
                "root_cause_category": r.root_cause_category,
                "explanation": r.explanation,
                "suggested_fix": r.suggested_fix,
                "confidence": r.confidence,
            }
        )
        print(f"[analyze_failures] {r.job_name} -> {r.root_cause_category}")
    return {"analyses": analyses}


def review_low_confidence_node(state: GraphState) -> GraphState:
    """HITL #1: pause for human review of any low-confidence diagnosis."""
    low_conf = [a for a in state["analyses"] if a["confidence"] < LOW_CONFIDENCE_THRESHOLD]

    if not low_conf:
        print("[review_low_confidence] all diagnoses above threshold, no review needed")
        return {}

    print(f"[review_low_confidence] {len(low_conf)} diagnosis(es) need human review")
    # Pauses graph execution here. Resumed with:
    #   Command(resume={job_name: "approve" | "<corrected explanation>"})
    responses: dict[str, str] = interrupt(
        {"type": "low_confidence_review", "items": low_conf}
    )

    updated = []
    for a in state["analyses"]:
        resp = responses.get(a["job_name"])
        a = dict(a)
        if resp == "approve":
            a["confidence"] = max(a["confidence"], 0.9)
        elif resp:
            a["explanation"] = f"[Human-corrected] {resp}"
            a["confidence"] = 1.0
        updated.append(a)
    return {"analyses": updated}


def propose_actions_node(state: GraphState) -> GraphState:
    actions: list[ProposedAction] = [
        {
            "job_name": a["job_name"],
            "action": ACTION_MAP.get(a["root_cause_category"], ACTION_MAP["unknown"]),
            "category": a["root_cause_category"],
        }
        for a in state["analyses"]
    ]
    return {"proposed_actions": actions}


def approve_actions_node(state: GraphState) -> GraphState:
    """HITL #2: pause for human approval before any action is executed."""
    print(f"[approve_actions] {len(state['proposed_actions'])} action(s) awaiting approval")
    # Pauses graph execution here. Resumed with:
    #   Command(resume={job_name: True | False})
    approvals: dict[str, bool] = interrupt(
        {"type": "action_approval", "actions": state["proposed_actions"]}
    )
    return {"action_approvals": approvals}


def execute_actions_node(state: GraphState) -> GraphState:
    results: list[ExecutionResult] = []
    for action in state["proposed_actions"]:
        approved = state["action_approvals"].get(action["job_name"], False)
        status = "executed" if approved else "skipped"
        print(f"[execute_actions] {status.upper()}: {action['action']} ({action['job_name']})")
        results.append({**action, "status": status})
    return {"execution_results": results}


def generate_report_node(state: GraphState) -> GraphState:
    lines = ["# Cloud Scheduler Failure Report", ""]
    exec_by_job = {r["job_name"]: r for r in state["execution_results"]}
    for a in state["analyses"]:
        lines.append(f"## {a['job_name']}  (confidence: {a['confidence']:.0%})")
        lines.append(f"- **Time:** {a['timestamp']}")
        lines.append(f"- **HTTP status:** {a['http_status']}")
        lines.append(f"- **Category:** {a['root_cause_category']}")
        lines.append(f"- **What happened:** {a['explanation']}")
        lines.append(f"- **Suggested fix:** {a['suggested_fix']}")
        exec_result = exec_by_job.get(a["job_name"])
        if exec_result:
            lines.append(f"- **Action:** {exec_result['action']} ({exec_result['status']})")
        lines.append("")
    report = "\n".join(lines)
    return {"report": report}


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("fetch_logs", fetch_logs_node)
    graph.add_node("analyze_failures", analyze_failures_node)
    graph.add_node("review_low_confidence", review_low_confidence_node)
    graph.add_node("propose_actions", propose_actions_node)
    graph.add_node("approve_actions", approve_actions_node)
    graph.add_node("execute_actions", execute_actions_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("fetch_logs")
    graph.add_edge("fetch_logs", "analyze_failures")
    graph.add_edge("analyze_failures", "review_low_confidence")
    graph.add_edge("review_low_confidence", "propose_actions")
    graph.add_edge("propose_actions", "approve_actions")
    graph.add_edge("approve_actions", "execute_actions")
    graph.add_edge("execute_actions", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile(checkpointer=MemorySaver())
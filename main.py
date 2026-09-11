from dotenv import load_dotenv
load_dotenv()

from langgraph.types import Command
from graph import build_graph


def handle_low_confidence_review(payload: dict) -> dict:
    print("\n--- HUMAN REVIEW NEEDED: low-confidence diagnoses ---")
    responses = {}
    for item in payload["items"]:
        print(f"\n  Job: {item['job_name']}  (confidence: {item['confidence']:.0%})")
        print(f"  Diagnosis: {item['explanation']}")
        ans = input("  Approve this diagnosis? (y/n): ").strip().lower()
        if ans == "y":
            responses[item["job_name"]] = "approve"
        else:
            responses[item["job_name"]] = input("  Enter corrected explanation: ").strip()
    return responses


def handle_action_approval(payload: dict) -> dict:
    print("\n--- HUMAN APPROVAL NEEDED: proposed actions ---")
    approvals = {}
    for action in payload["actions"]:
        print(f"\n  Job: {action['job_name']}")
        print(f"  Proposed action: {action['action']}")
        ans = input("  Approve this action? (y/n): ").strip().lower()
        approvals[action["job_name"]] = ans == "y"
    return approvals


def main():
    app = build_graph()
    config = {"configurable": {"thread_id": "rootcause-agent-run"}}

    result = app.invoke(
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

    # Resume loop: keep resolving interrupts until the graph completes
    while "__interrupt__" in result:
        interrupt_obj = result["__interrupt__"][0]
        payload = interrupt_obj.value

        if payload["type"] == "low_confidence_review":
            resume_value = handle_low_confidence_review(payload)
        elif payload["type"] == "action_approval":
            resume_value = handle_action_approval(payload)
        else:
            raise ValueError(f"Unknown interrupt type: {payload['type']}")

        result = app.invoke(Command(resume=resume_value), config=config)

    print("\n" + "=" * 60)
    print(result["report"])


if __name__ == "__main__":
    main()

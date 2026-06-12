import logging
from typing import Literal

from backend.src.agents.state import SharedState, AgentRole, TriggerType
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.supervisor")


def supervisor_decision(state: SharedState) -> dict:
    trigger = state.trigger_type
    if trigger == TriggerType.REACTIVE:
        prompt = (
            f"Given the HR query below, decide which agent should handle it.\n"
            f"Options: policy, action, anomaly, compliance.\n\n"
            f"Query: {state.query}\n"
            f"Reply with one word."
        )
        decision, _ = llm_call("supervisor", prompt, max_tokens=20, temperature=0)
        decision = decision.strip().lower()
    elif trigger == TriggerType.SCHEDULED:
        decision = "anomaly"
    else:
        decision = "compliance"

    valid = {"policy", "action", "anomaly", "compliance"}
    decision = decision if decision in valid else "policy"
    logger.info("Supervisor routed: query=%s -> %s", state.query[:50], decision)
    return {"current_agent": decision, "rl_selected_action": decision}

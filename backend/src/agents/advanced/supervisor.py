"""Supervisor agent that routes queries using LLM classification and RL bandit feedback."""

import logging

from backend.src.agents.state import SharedState, AgentRole, TriggerType
from backend.src.intelligence.rl_layer import rl_agent
from backend.src.utils.model_router import llm_call

logger = logging.getLogger("hr_ops.supervisor")


def supervisor_decision(state: SharedState) -> dict:
    """Route a query to the appropriate agent using LLM classification + LinUCB bandit.

    The LLM first classifies the query based on trigger type (reactive → LLM classify,
    scheduled → anomaly, otherwise → compliance). The LinUCB agent then re-ranks the
    decision using context features (query complexity, urgency) to balance exploration
    vs. exploitation. The final agent is written to ``current_agent``."""
    trigger = state.trigger_type
    
    if trigger == TriggerType.REACTIVE:
        history = state.messages
        history_context = ""
        if history:
            recent = history[-4:]
            history_context = "Conversation history:\n" + "\n".join(
                f"{m['role']}: {m['content'][:200]}" for m in recent
            ) + "\n\n"

        prompt = (
            f"{history_context}"
            f"Given the HR query below, decide which agent should handle it.\n"
            f"Options: policy, action, anomaly, compliance.\n\n"
            f"Query: {state.query}\n"
            f"Reply with one word."
        )
        llm_decision, _ = llm_call("supervisor", prompt, max_tokens=20, temperature=0)
        llm_decision = llm_decision.strip().lower()
    elif trigger == TriggerType.SCHEDULED:
        llm_decision = "anomaly"
    else:
        llm_decision = "compliance"

    valid = {"policy", "action", "anomaly", "compliance"}
    llm_decision = llm_decision if llm_decision in valid else "policy"

    rl_context = {
        "classification": llm_decision,
        "query": state.query,
        "query_complexity": min(len(state.query) / 200, 1.0),
        "urgent": 1.0 if any(kw in state.query.lower() for kw in ["urgent", "asap", "immediately"]) else 0.0,
    }

    decision = rl_agent.select_action(rl_context)
    logger.info(
        "Supervisor routed: query=%s -> rl=%s llm=%s",
        state.query[:50], decision, llm_decision,
    )
    return {"current_agent": decision, "rl_selected_action": decision, "rl_context": rl_context}

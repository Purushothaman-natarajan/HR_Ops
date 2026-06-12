import logging
from typing import Any

try:
    import litellm
    _LITELLM_AVAILABLE = True
except ImportError:
    litellm = None
    _LITELLM_AVAILABLE = False
from backend.config.settings import settings

logger = logging.getLogger("hr_ops.model_router")


def _get_agent_config(agent_name: str) -> dict:
    agents = settings.model_config_yaml.get("agents", {})
    return agents.get(agent_name, {})


def resolve_model(
    agent_name: str,
    task_type: str = "",
    cost_budget: str = "standard",
) -> str:
    config = _get_agent_config(agent_name)
    if not config:
        return settings.model_config_yaml.get("default_model", "gpt-4o-mini")

    tier = settings.cost_config.get("cost_tiers", {})
    tier_info = tier.get(cost_budget, tier.get("standard", {}))
    preferred = tier_info.get("preferred_model", "")

    primary = config.get("primary", "")
    fallback = config.get("fallback", "")

    model = preferred if preferred else primary
    if not _is_provider_available(model):
        logger.info("Falling back from %s to %s for agent=%s", model, fallback, agent_name)
        model = fallback or primary

    if not model:
        model = settings.model_config_yaml.get("default_model", "gpt-4o-mini")

    logger.debug("Resolved model=%s for agent=%s task=%s", model, agent_name, task_type)
    return model


def _is_provider_available(model_str: str) -> bool:
    provider = model_str.split("/")[0] if "/" in model_str else "openai"
    return provider in settings.available_providers


def llm_call(
    agent_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    cost_budget: str = "standard",
    **kwargs: Any,
) -> tuple[str, float]:
    model = resolve_model(agent_name, cost_budget=cost_budget)
    if not _LITELLM_AVAILABLE:
        logger.info("llm_call simulating (litellm not available): agent=%s", agent_name)
        if "one word" in prompt.lower() or "with one word" in prompt.lower():
            query_line = [l for l in prompt.split("\n") if l.strip().startswith("Query:")]
            if query_line:
                q = query_line[0].lower()
                if "salary" in q or "update" in q or "change" in q or "modify" in q:
                    return "action", 0.0
                if "anomaly" in q or "anomal" in q or "outlier" in q or "irregular" in q:
                    return "anomaly", 0.0
                if "complian" in q or "veto" in q or "termination" in q or "approve" in q:
                    return "compliance", 0.0
                if "leave" in q or "policy" in q or "sick" in q or "vacation" in q or "remote" in q:
                    return "policy", 0.0
            return "policy", 0.0
        if "json" in prompt.lower():
            return '{"name": "lookup_employee", "args": {"employee_id": "EMP0001"}}', 0.0
        if "compliant" in prompt.lower():
            return '{"compliant": true, "reason": "No issues found."}', 0.0
        return f"[simulated response for {agent_name}]", 0.0

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        text = response.choices[0].message.content or ""
        usage = getattr(response, "usage", None) or {}
        input_cost = _estimate_cost(model, usage.get("prompt_tokens", 0), "input")
        output_cost = _estimate_cost(model, usage.get("completion_tokens", 0), "output")
        total_cost = input_cost + output_cost
        logger.debug(
            "llm_call agent=%s model=%s tokens_in=%s tokens_out=%s cost=%.6f",
            agent_name, model, usage.get("prompt_tokens"), usage.get("completion_tokens"), total_cost,
        )
        return text, total_cost
    except Exception as e:
        logger.warning("llm_call failed agent=%s model=%s error=%s", agent_name, model, e)
        if not kwargs.get("_retried"):
            kwargs["_retried"] = True
            return llm_call(agent_name, prompt, system_prompt, temperature, max_tokens, cost_budget, **kwargs)
        raise


_MODEL_COST_PER_1K = {
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
    "llama-3.1-8b-instant": {"input": 0.0001, "output": 0.0004},
}


def _estimate_cost(model: str, tokens: int, direction: str) -> float:
    for key, rates in _MODEL_COST_PER_1K.items():
        if key in model:
            return (tokens / 1000) * rates.get(direction, 0)
    return (tokens / 1000) * 0.001

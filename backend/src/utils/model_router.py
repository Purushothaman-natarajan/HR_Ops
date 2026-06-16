"""Model routing with NVIDIA NIM direct API path and litellm fallback, plus config-driven cost estimation."""

import logging
import sys
from typing import Any

import httpx

if "litellm" in sys.modules:
    litellm = sys.modules["litellm"]
    _LITELLM_AVAILABLE = True
else:
    try:
        import litellm
        _LITELLM_AVAILABLE = True
    except ImportError:
        litellm = None  # type: ignore[assignment]
        _LITELLM_AVAILABLE = False

from backend.src.core.settings import settings
from backend.src.core.exceptions import ModelNotAvailableError
from backend.src.guardrails.registry import guardrail_registry

logger = logging.getLogger("hr_ops.model_router")

# Connection pool for NVIDIA API (reuses HTTP connections)
_NVIDIA_HTTP_CLIENT: httpx.AsyncClient | None = None


def _get_nvidia_http_client() -> httpx.AsyncClient:
    """Get or create a shared httpx client for NVIDIA API with connection pooling."""
    global _NVIDIA_HTTP_CLIENT
    if _NVIDIA_HTTP_CLIENT is None or _NVIDIA_HTTP_CLIENT.is_closed:
        timeout = httpx.Timeout(
            connect=10.0,
            read=settings.agui_timeout_seconds or 300.0,
            write=10.0,
            pool=5.0,
        )
        limits = httpx.Limits(
            max_connections=20,
            max_keepalive_connections=10,
            keepalive_expiry=30.0,
        )
        _NVIDIA_HTTP_CLIENT = httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            http2=True,
        )
    return _NVIDIA_HTTP_CLIENT


async def close_nvidia_http_client() -> None:
    """Close the shared NVIDIA HTTP client (call on shutdown)."""
    global _NVIDIA_HTTP_CLIENT
    if _NVIDIA_HTTP_CLIENT is not None and not _NVIDIA_HTTP_CLIENT.is_closed:
        await _NVIDIA_HTTP_CLIENT.aclose()
        _NVIDIA_HTTP_CLIENT = None


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


_MSG_LITELLM_MISSING = (
    "The AI model backend (litellm) is not installed. "
    "Please contact the administrator to install litellm and configure model API keys."
)
_MSG_NVIDIA_LITELLM_FALLBACK = (
    "The NVIDIA AI model call failed and the fallback LLM backend (litellm) is not available. "
    "Please contact the administrator to check the NVIDIA API configuration or install litellm."
)
_MSG_AUTH_FAILURE = (
    "The AI model API key is missing or invalid. "
    "Please contact the administrator to configure the correct model API key."
)
_MSG_RETRY_FAILURE = (
    "The AI model call failed after retry. "
    "Please contact the administrator to check the model configuration."
)


def _estimate_cost(model: str, tokens: int, direction: str) -> float:
    costs = settings.cost_config.get("model_costs_per_1k", {})
    sorted_keys = sorted(costs.keys(), key=len, reverse=True)
    for key in sorted_keys:
        if model.startswith(key):
            return (tokens / 1000) * costs[key].get(direction, 0)
    return (tokens / 1000) * 0.001


async def _call_nvidia(
    agent_name: str,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str = "high",
    top_p: float = 1.0,
) -> tuple[str, float]:
    """Call NVIDIA NIM chat completions via the OpenAI-compatible API with streaming (connection pooled)."""
    from openai import AsyncOpenAI

    http_client = _get_nvidia_http_client()
    client = AsyncOpenAI(
        api_key=settings.nvidia_api_key,
        base_url="https://integrate.api.nvidia.com/v1",
        http_client=http_client,
    )
    model_name = model.removeprefix("nvidia/")

    extra_body = {}
    if reasoning_effort and reasoning_effort != "none":
        extra_body["chat_template_kwargs"] = {
            "thinking": True,
            "reasoning_effort": reasoning_effort,
        }

    response = await client.chat.completions.create(
        model=model_name,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=max_tokens,
        temperature=temperature,
        top_p=top_p,
        stream=False,
        extra_body=extra_body,
    )

    message = response.choices[0].message  # type: ignore[union-attr]
    reasoning = (
        getattr(message, "reasoning", None)
        or getattr(message, "reasoning_content", None)
    )
    if reasoning:
        logger.debug("nvidia_call reasoning agent=%s model=%s reasoning=%s", agent_name, model, reasoning)
    text = message.content or ""
    input_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
    output_tokens = len(text) // 4
    cost = _estimate_cost(model, input_tokens, "input")
    cost += _estimate_cost(model, output_tokens, "output")
    logger.debug(
        "nvidia_call agent=%s model=%s tokens_in=%s tokens_out=%s cost=%.6f reasoning=%s top_p=%.2f",
        agent_name, model, input_tokens, output_tokens, cost, reasoning_effort, top_p,
    )
    return text, cost


def _litellm_call(
    agent_name: str,
    model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    **kwargs: Any,
) -> tuple[str, float]:
    """Call an LLM via litellm with cost estimation."""
    if not _LITELLM_AVAILABLE:
        logger.error("litellm_call failed: litellm not installed (agent=%s)", agent_name)
        raise ModelNotAvailableError(_MSG_LITELLM_MISSING)

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
            "litellm_call agent=%s model=%s tokens_in=%s tokens_out=%s cost=%.6f",
            agent_name, model, usage.get("prompt_tokens"), usage.get("completion_tokens"), total_cost,
        )
        return text, total_cost
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("auth", "api key", "unauthorized", "403", "401", "permission", "credential")):
            logger.error("litellm_call auth failure agent=%s model=%s error=%s", agent_name, model, e)
            raise ModelNotAvailableError(_MSG_AUTH_FAILURE) from e
        raise


async def llm_call(
    agent_name: str,
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.0,
    max_tokens: int = 1024,
    cost_budget: str = "standard",
    reasoning_effort: str | None = None,
    top_p: float | None = None,
    **kwargs: Any,
) -> tuple[str, float]:
    """Make an LLM call — routes to NVIDIA NIM directly for nvidia/ models, otherwise uses litellm."""
    model = resolve_model(agent_name, cost_budget=cost_budget)

    agent_config = _get_agent_config(agent_name)
    if reasoning_effort is None:
        reasoning_effort = agent_config.get("reasoning_effort", "high")
    if top_p is None:
        top_p = agent_config.get("top_p", 1.0)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    fallback_model = agent_config.get("fallback", "")

    estimated_input_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
    estimated_cost = _estimate_cost(model, estimated_input_tokens, "input")
    model_gr = guardrail_registry.check_model({
        "estimated_cost_usd": estimated_cost,
        "timeout_seconds": max_tokens // 10,
    })
    if not model_gr.passed:
        raise ModelNotAvailableError(f"Model guardrail blocked: {model_gr.message}")

    if model.startswith("nvidia/"):
        return await _call_nvidia_with_fallback(
            agent_name, model, fallback_model, messages, temperature, max_tokens,
            reasoning_effort, top_p, kwargs,
        )

    return await _call_with_retry(agent_name, model, fallback_model, messages, temperature, max_tokens, kwargs)


async def _call_nvidia_with_fallback(
    agent_name: str,
    model: str,
    fallback_model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    reasoning_effort: str,
    top_p: float,
    kwargs: dict,
) -> tuple[str, float]:
    """Call NVIDIA NIM; on failure retry once, then fall back to agent fallback model via litellm."""
    last_error: Exception | None = None
    try:
        return await _call_nvidia(agent_name, model, messages, temperature, max_tokens, reasoning_effort, top_p)
    except Exception as e:
        last_error = e
        err_str = str(e).lower()
        if any(kw in err_str for kw in ("auth", "api key", "unauthorized", "403", "401")):
            logger.error("nvidia_call auth failure agent=%s model=%s error=%s", agent_name, model, e)
            raise ModelNotAvailableError(_MSG_AUTH_FAILURE) from e

        logger.warning("nvidia_call failed, retrying agent=%s model=%s error=%s", agent_name, model, e)
        try:
            return await _call_nvidia(agent_name, model, messages, temperature, max_tokens, reasoning_effort, top_p)
        except Exception as e2:
            last_error = e2
            logger.error("nvidia_call retry also failed agent=%s model=%s error=%s", agent_name, model, e2)

    if fallback_model:
        if not _is_provider_available(fallback_model):
            logger.warning("Fallback provider unavailable for agent=%s, fallback=%s", agent_name, fallback_model)
        elif fallback_model.startswith("nvidia/"):
            logger.warning("NVIDIA primary unavailable for agent=%s, falling back to %s", agent_name, fallback_model)
            try:
                return await _call_nvidia(
                    agent_name,
                    fallback_model,
                    messages,
                    temperature,
                    max_tokens,
                    "none",
                    top_p,
                )
            except Exception as fallback_error:
                logger.error(
                    "nvidia fallback failed agent=%s model=%s error=%s",
                    agent_name, fallback_model, fallback_error,
                )
                last_error = fallback_error
        else:
            logger.warning("NVIDIA unavailable for agent=%s, falling back to %s", agent_name, fallback_model)
            try:
                return await _call_with_retry(agent_name, fallback_model, "", messages, temperature, max_tokens, kwargs)
            except ModelNotAvailableError as mae:
                if not _LITELLM_AVAILABLE:
                    raise ModelNotAvailableError(_MSG_NVIDIA_LITELLM_FALLBACK) from mae
                raise

    raise ModelNotAvailableError(
        f"{_MSG_RETRY_FAILURE} (agent={agent_name}, model={model})"
    ) from last_error


async def _call_with_retry(
    agent_name: str,
    model: str,
    fallback_model: str,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    kwargs: dict,
) -> tuple[str, float]:
    """Call via litellm with one automatic retry on failure, then agent fallback if configured."""
    litellm_retried = False
    try:
        return _litellm_call(agent_name, model, messages, temperature, max_tokens, **kwargs)
    except ModelNotAvailableError:
        raise
    except Exception as e:
        if not litellm_retried:
            litellm_retried = True
            logger.warning("litellm_call failed, retrying agent=%s model=%s error=%s", agent_name, model, e)
            try:
                return _litellm_call(agent_name, model, messages, temperature, max_tokens, **kwargs)
            except Exception:
                pass

        if fallback_model and _is_provider_available(fallback_model):
            logger.warning("litellm unavailable for agent=%s, falling back to %s", agent_name, fallback_model)
            try:
                return _litellm_call(agent_name, fallback_model, messages, temperature, max_tokens, **kwargs)
            except Exception as e3:
                raise ModelNotAvailableError(
                    f"{_MSG_RETRY_FAILURE} (agent={agent_name}, model={fallback_model})"
                ) from e3

        raise ModelNotAvailableError(
            f"{_MSG_RETRY_FAILURE} (agent={agent_name}, model={model})"
        ) from e

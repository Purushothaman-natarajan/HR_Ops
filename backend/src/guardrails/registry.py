"""Central registry for all guardrail checks across input, output, tool, and model."""

from __future__ import annotations

import logging
from typing import Any, Callable

from backend.src.agents.state import GuardrailResult

logger = logging.getLogger("hr_ops.guardrails")

GuardrailFn = Callable[[dict], tuple[bool, str]]


class GuardrailRegistry:
    """Manages registration and execution of guardrail check functions."""

    def __init__(self):
        self._input_checks: list[GuardrailFn] = []
        self._output_checks: list[GuardrailFn] = []
        self._tool_checks: list[GuardrailFn] = []
        self._model_checks: list[GuardrailFn] = []

    def register_input(self, fn: GuardrailFn, name: str | None = None):
        """Register a function as an input guardrail check."""
        self._input_checks.append(fn)
        logger.debug("Registered input guardrail: %s", name or fn.__name__)

    def register_output(self, fn: GuardrailFn, name: str | None = None):
        """Register a function as an output guardrail check."""
        self._output_checks.append(fn)
        logger.debug("Registered output guardrail: %s", name or fn.__name__)

    def register_tool(self, fn: GuardrailFn, name: str | None = None):
        """Register a function as a tool guardrail check."""
        self._tool_checks.append(fn)
        logger.debug("Registered tool guardrail: %s", name or fn.__name__)

    def register_model(self, fn: GuardrailFn, name: str | None = None):
        """Register a function as a model guardrail check."""
        self._model_checks.append(fn)
        logger.debug("Registered model guardrail: %s", name or fn.__name__)

    def check_input(self, context: dict) -> GuardrailResult:
        """Run all registered input guardrails. Returns first failure or success."""
        for check in self._input_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(
                    passed=False, guardrail_type="input", message=msg
                )
        return GuardrailResult(passed=True, guardrail_type="input")

    def check_output(self, context: dict) -> GuardrailResult:
        """Run all registered output guardrails. Returns first failure or success."""
        for check in self._output_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(
                    passed=False, guardrail_type="output", message=msg
                )
        return GuardrailResult(passed=True, guardrail_type="output")

    def check_tool(self, context: dict) -> GuardrailResult:
        """Run all registered tool guardrails. Returns first failure or success."""
        for check in self._tool_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(
                    passed=False, guardrail_type="tool", message=msg
                )
        return GuardrailResult(passed=True, guardrail_type="tool")

    def check_model(self, context: dict) -> GuardrailResult:
        """Run all registered model guardrails. Returns first failure or success."""
        for check in self._model_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(
                    passed=False, guardrail_type="model", message=msg
                )
        return GuardrailResult(passed=True, guardrail_type="model")

    def run_all(self, context: dict) -> list[tuple[str, GuardrailResult]]:
        """Run all guardrail types and return a list of (type, result) tuples."""
        return [
            ("input", self.check_input(context)),
            ("output", self.check_output(context)),
            ("tool", self.check_tool(context)),
            ("model", self.check_model(context)),
        ]


guardrail_registry = GuardrailRegistry()

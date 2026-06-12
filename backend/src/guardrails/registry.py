from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("hr_ops.guardrails")


GuardrailFn = Callable[[dict], tuple[bool, str]]


@dataclass
class GuardrailResult:
    passed: bool
    message: str = ""
    metadata: dict = field(default_factory=dict)


class GuardrailRegistry:
    def __init__(self):
        self._input_checks: list[GuardrailFn] = []
        self._output_checks: list[GuardrailFn] = []
        self._tool_checks: list[GuardrailFn] = []
        self._model_checks: list[GuardrailFn] = []

    def register_input(self, fn: GuardrailFn, name: str | None = None):
        self._input_checks.append(fn)
        logger.debug("Registered input guardrail: %s", name or fn.__name__)

    def register_output(self, fn: GuardrailFn, name: str | None = None):
        self._output_checks.append(fn)
        logger.debug("Registered output guardrail: %s", name or fn.__name__)

    def register_tool(self, fn: GuardrailFn, name: str | None = None):
        self._tool_checks.append(fn)
        logger.debug("Registered tool guardrail: %s", name or fn.__name__)

    def register_model(self, fn: GuardrailFn, name: str | None = None):
        self._model_checks.append(fn)
        logger.debug("Registered model guardrail: %s", name or fn.__name__)

    def check_input(self, context: dict) -> GuardrailResult:
        for check in self._input_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(passed=False, message=msg)
        return GuardrailResult(passed=True)

    def check_output(self, context: dict) -> GuardrailResult:
        for check in self._output_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(passed=False, message=msg)
        return GuardrailResult(passed=True)

    def check_tool(self, context: dict) -> GuardrailResult:
        for check in self._tool_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(passed=False, message=msg)
        return GuardrailResult(passed=True)

    def check_model(self, context: dict) -> GuardrailResult:
        for check in self._model_checks:
            passed, msg = check(context)
            if not passed:
                return GuardrailResult(passed=False, message=msg)
        return GuardrailResult(passed=True)

    def run_all(self, context: dict) -> list[tuple[str, GuardrailResult]]:
        return [
            ("input", self.check_input(context)),
            ("output", self.check_output(context)),
            ("tool", self.check_tool(context)),
            ("model", self.check_model(context)),
        ]


guardrail_registry = GuardrailRegistry()

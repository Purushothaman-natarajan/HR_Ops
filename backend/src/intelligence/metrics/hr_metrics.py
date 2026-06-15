"""DSPy metric for evaluating HR answer accuracy and policy compliance."""

import dspy


class HRApprovalMetric(dspy.Signature):
    """Evaluate whether the HR answer is accurate and policy-compliant."""

    question: str = dspy.InputField()
    answer: str = dspy.InputField()
    score: float = dspy.OutputField(desc="0.0 to 1.0")
    feedback: str = dspy.OutputField(desc="Reasoning for the score")


def approval_rate(example: dspy.Example, prediction: dspy.Prediction, trace=None) -> float:
    """Metric: was the output approved (1.0) or rejected (0.0)?"""
    expected = getattr(example, "classification", None) or getattr(example, "label", None)
    predicted = getattr(prediction, "classification", None) or getattr(prediction, "answer", None)
    if expected and predicted:
        return 1.0 if str(expected).strip().lower() == str(predicted).strip().lower() else 0.0
    return 0.5

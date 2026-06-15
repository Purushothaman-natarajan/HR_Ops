"""DSPy signature for classifying HR queries into policy, action, anomaly, or compliance."""

import dspy


class TriageSignature(dspy.Signature):
    """Classify an HR query into one of: policy, action, anomaly, compliance."""

    query: str = dspy.InputField(desc="The HR query text")
    classification: str = dspy.OutputField(
        desc="One of: policy, action, anomaly, compliance"
    )

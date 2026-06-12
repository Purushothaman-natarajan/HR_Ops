import dspy


class NarrativeSignature(dspy.Signature):
    """Generate a concise narrative summary of anomaly detection results for HR management."""

    anomalies: str = dspy.InputField(desc="List of detected anomalies with severity")
    narrative: str = dspy.OutputField(desc="Concise narrative summary")

"""DSPy signature for answering HR policy questions using retrieved context."""

import dspy


class RAGSignature(dspy.Signature):
    """Answer an HR policy question based on retrieved policy documents."""

    context: str = dspy.InputField(desc="Retrieved HR policy snippets")
    question: str = dspy.InputField(desc="The HR policy question")
    answer: str = dspy.OutputField(desc="Policy-backed answer")

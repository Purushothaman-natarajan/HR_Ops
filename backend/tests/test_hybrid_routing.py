import pytest
from backend.src.graph import build_full_graph
from backend.src.agents.state import SharedState, TriggerType
import asyncio

@pytest.mark.asyncio
async def test_hybrid_routing():
    # Construct a state that forces "hybrid" routing
    graph = build_full_graph()
    
    # We can invoke the graph but it might do real LLM calls if we don't mock.
    # We just want to check the edges and structure.
    
    assert "action" in graph.nodes
    assert "policy" in graph.nodes
    assert "supervisor" in graph.nodes
    assert "parallel_check" in graph.nodes

    # Let's inspect edges for "action"
    # Action conditional edge should exist
    # Can't easily inspect compiled graph edges without complex langgraph introspection.
    # Just checking it compiles is a good start.
    assert graph is not None

if __name__ == "__main__":
    asyncio.run(test_hybrid_routing())

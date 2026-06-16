import asyncio
from backend.src.services.graph_service import run_graph
from backend.src.utils.alert_store import alert_store
from backend.src.memory.episodic_memory import episodic_memory

async def test_alert():
    query = "Run anomaly detection across all HR datasets"
    result = await run_graph(query, trigger="scheduled")
    print("Graph execution complete.")
    alert_store.add_alert(query, "scheduled", result)
    print("Alert store added.")
    episodic_memory.store_incident("scheduled", query, result.get("final_response", ""))
    print("Episodic memory stored.")

if __name__ == "__main__":
    asyncio.run(test_alert())

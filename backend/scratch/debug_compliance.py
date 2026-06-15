import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.src.services.conversation_service import session_store

async def main():
    query = "How many annual leave days do I get per month?"
    print(f"Running query: {query}")
    session = session_store.create_session(query, mode="advanced")
    result = await session_store.run_turn_async(session["session_id"], query)
    
    print("\n--- Execution Results ---")
    print(f"Response: {result.get('response')}")
    print("\n--- Trace Events ---")
    for t in result.get("trace_events", []):
        print(f"\nNode: {t.get('node')}")
        print(f"Agent Role: {t.get('agent_role')}")
        print(f"Output: {t.get('output_text')}")
        if t.get('node') == 'compliance_node':
            print(f"Compliance Output Details: {t}")

if __name__ == "__main__":
    asyncio.run(main())

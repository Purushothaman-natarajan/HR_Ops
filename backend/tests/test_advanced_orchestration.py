import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient
from backend.src.main import app
from backend.src.agents.state import SharedState, TriggerType
from backend.src.agents.advanced.supervisor import supervisor_decision
from backend.src.utils.alert_store import alert_store

client = TestClient(app)

@pytest.mark.asyncio
async def test_system_trigger_routing_by_supervisor():
    """Verify that TriggerType.SYSTEM triggers LLM classification in supervisor_decision."""
    state = SharedState(
        query="Discrepancy in salary for EMP0001",
        trigger_type=TriggerType.SYSTEM,
        messages=[]
    )
    
    # Mock llm_call to return "action"
    with patch("backend.src.agents.advanced.supervisor.llm_call", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = ("action", 0.001)
        
        result = await supervisor_decision(state)
        
        # Should call LLM classifier rather than defaulting to compliance
        mock_llm.assert_called_once()
        assert result["current_agent"] == "action"


def test_system_alert_store_deduplication():
    """Verify that system trigger alerts are deduplicated by query in alert_store."""
    alert_store.clear_cache()
    alert_store._alerts = []
    
    # Add initial alert
    alert1 = alert_store.add_alert(
        query="Alert: Salary mismatch for EMP0001",
        trigger_type="system",
        result={"final_response": "Discrepancy resolved.", "anomaly_results": []}
    )
    assert len(alert_store.get_alerts()) == 1
    
    # Add identical query alert (should update in-place)
    alert2 = alert_store.add_alert(
        query="Alert: Salary mismatch for EMP0001",
        trigger_type="system",
        result={"final_response": "Discrepancy resolved. Salary adjusted by AED 800.", "anomaly_results": []}
    )
    
    alerts = alert_store.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]["id"] == alert1["id"]
    assert alerts[0]["result"]["final_response"] == "Discrepancy resolved. Salary adjusted by AED 800."


def test_get_system_summary_api():
    """Verify that GET /alerts/system-summary returns the consolidated system alerts summary."""
    alert_store.clear_cache()
    alert_store._alerts = []
    
    # Add some mock system alerts
    alert_store.add_alert(
        query="Alert: High absence for EMP0002",
        trigger_type="system",
        result={"final_response": "Bob has 50% absence in June.", "anomaly_results": []}
    )
    alert_store.add_alert(
        query="Alert: Salary mismatch for EMP0001",
        trigger_type="system",
        result={"final_response": "Salary short by AED 800.", "anomaly_results": []}
    )
    
    r = client.get("/alerts/system-summary")
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    summary = data["data"]["summary"]
    
    assert "High absence for EMP0002" in summary
    assert "Salary mismatch for EMP0001" in summary
    assert "Salary short by AED 800" in summary


@pytest.mark.asyncio
async def test_cooperative_yield_no_active_queries():
    """Verify that cooperative_yield does not block when no user queries are active."""
    import asyncio
    from backend.src.services.graph_service import _active_user_queries, cooperative_yield
    
    # Ensure active queries is 0
    assert _active_user_queries == 0
    
    # Executing cooperative_yield for scheduled trigger should finish instantly
    await asyncio.wait_for(cooperative_yield("scheduled"), timeout=0.1)


@pytest.mark.asyncio
async def test_cooperative_yield_with_active_queries():
    """Verify that cooperative_yield pauses scheduled tasks when a user query is active."""
    import asyncio
    from backend.src.services.graph_service import UserQueryTracker, cooperative_yield

    yielded = False

    async def run_scheduled():
        nonlocal yielded
        await cooperative_yield("scheduled")
        yielded = True

    # Start a user query context
    async with UserQueryTracker("reactive"):
        task = asyncio.create_task(run_scheduled())
        
        # Let the loop run; the scheduled task should be blocked
        await asyncio.sleep(0.05)
        assert not yielded
        assert not task.done()
        
    # Once UserQueryTracker exits, the task should resume and complete
    await asyncio.wait_for(task, timeout=0.5)
    assert yielded


@pytest.mark.asyncio
async def test_scheduler_startup_delay():
    """Verify that AnomalyScheduler sleeps for the startup delay on boot."""
    import asyncio
    from backend.src.services.scheduler import AnomalyScheduler
    
    scheduler_instance = AnomalyScheduler(interval_seconds=10)
    
    with patch("backend.src.core.settings.settings.app_config", {"scheduler": {"startup_delay_seconds": 1}}):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            task = asyncio.create_task(scheduler_instance._run_scheduled_anomaly_detection())
            await asyncio.sleep(0.01)
            
            # The scheduler should have called sleep with 1 second startup delay
            mock_sleep.assert_any_call(1)
            task.cancel()

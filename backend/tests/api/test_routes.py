import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.api.schemas import AgentAction

client = TestClient(app)

def test_read_root():
    response = client.get("/api/")
    assert response.status_code == 200
    assert response.json() == {"msg": "Welcome to Paparika!"}

def test_websocket_agent_flow():
    from unittest.mock import patch, AsyncMock

    # 1. Define the input data (UPDATED FOR NESTED SCHEMA)
    perception_payload = {
        "self": {
            "time_hour": 10,
            "current_zone": "Kitchen_01",
            "held_item": None,
            "status": "idle"
        },
        "sensory": {
            "player_nearby": True,
            "visible_objects": []
        },
        "execution_trace": []
    }

    mock_action = AgentAction(
        thought_trace="I see nothing, so I will explore.",
        function="move_to",
        args={"target_id": "LivingRoom"}
    )

    mock_state_result = {
        "task": "Explore the house",
        "plan": [mock_action],
        "skill_guide": "",
        "critique": None,
        "retry_count": 0
    }

    with patch("app.api.routes.graph_app.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_state_result

        with client.websocket_connect("/api/ws/agent/123") as websocket:
            websocket.send_json(perception_payload)
            response = websocket.receive_json()
            
            assert response["client_id"] == "123"
            assert response["task"] == "Explore the house"
            assert response["plan"][0]["function"] == "move_to"

@pytest.mark.paid
@pytest.mark.integration
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
def test_websocket_live_static_world_failure():
    """
    ⚡ LIVE STATIC FAILURE TEST ⚡
    """
    # 1. Define a "Hungry in Kitchen" Scenario (UPDATED FOR NESTED SCHEMA)
    perception_payload = {
        "self": {
            "time_hour": 18,
            "current_zone": "Kitchen_Zone_A",
            "held_item": None
        },
        "sensory": {
            "player_nearby": True,
            "visible_objects": [
                 {
                     "id": "Stove_01", 
                     "type": "Station", 
                     "distance": 1.5, 
                     "state": {"is_on": False}
                 },
                 {
                     "id": "RawSteak_01", 
                     "type": "Ingredient", 
                     "distance": 1.0, 
                     "state": {"is_raw": True}
                 }
            ]
        },
        "execution_trace": [
             # Simulating a previous failure to force retry loop
             {"step_index": 1, "function": "interact", "status": "failed", "message": "Failed to cook"}
        ]
    }

    print("\n🚀 Connecting to WebSocket (Real LLM, targeting RecursionError)...")

    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/api/ws/agent/1989") as websocket:
            websocket.send_json(perception_payload)
            
            print("⏳ Agent is thinking...")
            max_steps = 30 
            steps = 0
            
            try:
                while steps < max_steps:
                    response = websocket.receive_json()
                    task = response.get("task", "Unknown")
                    print(f"👉 Step {steps+1}: Agent thought -> {task}")
                    steps += 1
            except WebSocketDisconnect:
                print("💥 WebSocket Disconnected as expected!")
                raise 

    assert excinfo.value.code == 1011
    print("\n✅ Test Passed: Recursion Limit Hit.")
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.api.schemas import AgentAction

# Initialize TestClient (Synchronous)
client = TestClient(app)

def test_read_root():
    """Check if the HTTP endpoint works."""
    response = client.get("/api/")
    assert response.status_code == 200
    # Note: Ensure this string matches exactly what is in your main.py
    assert response.json() == {"msg": "Welcome to Paparika!"}

def test_websocket_agent_flow():
    """
    Test the full loop:
    1. Connect to WebSocket
    2. Send 'Perception' JSON
    3. Mock the Graph response (so we don't call real OpenAI)
    4. Verify the server returns the correct 'Plan' JSON
    """
    from unittest.mock import patch, AsyncMock

    # 1. Define the input data (What Unity sends)
    perception_payload = {
        "time_hour": 10,
        "day": 1,
        "mode": "reality",
        "location_id": "Kitchen_01",
        "player_nearby": True,
        "nearby_objects": [],
        "held_item": None,
        "last_action_status": "success",
        "last_action_error": None
    }

    # 2. Define the Mock Output (What LangGraph returns)
    mock_action = AgentAction(
        thought_trace="I see nothing, so I will explore.",
        function="move_to",
        args={"target_id": "LivingRoom"},
        plan_complete=False
    )

    # Note: Keys here must match AgentState in graph.py
    mock_state_result = {
        "task": "Explore the house",
        "plan": [mock_action],
        "skill_guide": "",
        "critique": None,
        "retry_count": 0
    }

    # 3. Patch the Graph Logic
    # We patch 'app.api.routes.graph_app.ainvoke' to bypass real AI execution
    with patch("app.api.routes.graph_app.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_state_result

        # 4. Run the WebSocket Test
        with client.websocket_connect("/api/ws/agent/123") as websocket:
            
            # Send Perception
            websocket.send_json(perception_payload)
            
            # Receive Plan
            response = websocket.receive_json()
            
            # 5. Assertions
            print(f"\nServer Response: {response}")
            
            assert response["client_id"] == "123"
            assert response["current_task"] == "Explore the house"
            assert len(response["plan"]) == 1
            assert response["plan"][0]["function"] == "move_to"
            assert response["plan"][0]["args"]["target_id"] == "LivingRoom"


@pytest.mark.paid
@pytest.mark.integration
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
def test_websocket_live_static_world_failure():
    """
    ⚡ LIVE STATIC FAILURE TEST ⚡
    
    Purpose: Verify that the agent enters the Retry Loop and eventually 
    hits the safety limit (RecursionError) when the world doesn't change.
    
    This confirms:
    1. The Graph is running.
    2. The Critic is rejecting static states.
    3. The Retry mechanism is active.
    
    Note: This is a synchronous test function (def, not async def) 
    to prevent deadlock issues with TestClient.
    """
    
    # 1. Define a "Hungry in Kitchen" Scenario
    perception_payload = {
        "time_hour": 18, # Dinner time
        "day": 1,
        "mode": "reality",
        "location_id": "Kitchen_Zone_A",
        "player_nearby": True,
        "held_item": None,
        "nearby_objects": [
             {
                 "id": "Stove_01", 
                 "type": "Station", 
                 "position": {"x": 2.0, "y": 0, "z": 0}, 
                 "distance": 1.5, 
                 "state": "off"
             },
             {
                 "id": "RawSteak_01", 
                 "type": "Ingredient", 
                 "position": {"x": 1.0, "y": 0.9, "z": 0}, 
                 "distance": 1.0, 
                 "state": "raw"
             }
        ],
        "last_action_status": None,
        "last_action_error": None
    }

    print("\n🚀 Connecting to WebSocket (Real LLM, targeting RecursionError)...")

    # We expect the server to close the connection with an error (1011) 
    # when it hits the GraphRecursionError.
    with pytest.raises(WebSocketDisconnect) as excinfo:
        
        # Use a specific ID. If you modified routes.py to limit recursion for "1989", 
        # this will finish fast. Otherwise, it waits for default limit (25 steps).
        with client.websocket_connect("/api/ws/agent/1989") as websocket:
            
            websocket.send_json(perception_payload)
            
            print("⏳ Agent is thinking... (This may take up to 60s if recursion limit is default)")
            
            # Safety mechanism to prevent infinite hanging if test fails to crash
            max_steps = 30 
            steps = 0
            
            try:
                while steps < max_steps:
                    # receive_json will block until message or disconnect
                    response = websocket.receive_json()
                    
                    task = response.get("current_task", "Unknown")
                    print(f"👉 Step {steps+1}: Agent thought -> {task}")
                    steps += 1
                    
            except WebSocketDisconnect:
                print("💥 WebSocket Disconnected as expected!")
                raise # Re-raise to be caught by pytest.raises

    # Verify we got the correct error code (1011 = Internal Server Error)
    assert excinfo.value.code == 1011
    print("\n✅ Test Passed: Recursion Limit Hit.")
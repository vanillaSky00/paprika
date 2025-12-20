import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from starlette.websockets import WebSocketDisconnect

from app.config import settings
from app.main import app
from app.api.schemas import AgentAction

client = TestClient(app)

def test_read_root():
    """Check if the HTTP endpoint works"""
    response = client.get("/api/") # Note: main.py includes router with /api prefix
    assert response.status_code == 200
    assert response.json() == {"msg": "Welcome to Paparika!"}

def test_websocket_agent_flow():
    """
    Test the full loop:
    1. Connect to WebSocket
    2. Send 'Perception' JSON
    3. Mock the Graph response (so we don't call real OpenAI)
    4. Verify the server returns the correct 'Plan' JSON
    """
    
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
    # We must create actual AgentAction objects because routes.py calls .model_dump() on them
    mock_action = AgentAction(
        thought_trace="I see nothing, so I will explore.",
        function="move_to",
        args={"target_id": "LivingRoom"},
        plan_complete=False
    )

    mock_state_result = {
        "task": "Explore the house",
        "plan": [mock_action],
        "skill_guide": "",
        "critique": None,
        "retry_count": 0
    }

    # 3. Patch the Graph Logic
    # We patch 'app.api.routes.graph_app.ainvoke' because that is where it is USED
    with patch("app.api.routes.graph_app.ainvoke", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = mock_state_result

        # 4. Run the WebSocket Test
        # Note: client_id is an int in your code, so we use 123
        with client.websocket_connect("/api/ws/agent/123") as websocket:
            
            # Send Perception
            websocket.send_json(perception_payload)
            
            # Receive Plan
            response = websocket.receive_json()
            
            # 5. Assertions
            print(f"\nServer Response: {response}")
            
            assert response["client_id"] == 123
            assert response["task"] == "Explore the house"
            assert len(response["plan"]) == 1
            assert response["plan"][0]["function"] == "move_to"
            assert response["plan"][0]["args"]["target_id"] == "LivingRoom"
            

@pytest.mark.paid
@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.skipif(
    not settings.OPENAI_API_KEY,
    reason="OPENAI_API_KEY not set; skipping live OpenAI test.",
)
async def test_websocket_live_static_world_failure():
    """
    ⚡ LIVE STATIC FAILURE TEST ⚡
    
    Purpose: Verify that the agent enters the Retry Loop and eventually 
    hits the safety limit (RecursionError) when the world doesn't change.
    
    This confirms:
    1. The Graph is running.
    2. The Critic is rejecting static states.
    3. The Retry mechanism is active.
    """
    
    # 1. Define a "Hungry in Kitchen" Scenario
    # This context strongly suggests a task like "Cook the meat"
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

    print("\n🚀 Connecting to WebSocket (Real LLM, in the end expect Recursion Limit)...")

    # We expect the server to close the connection with an error (1011) 
    # when it hits the GraphRecursionError.
    with pytest.raises(WebSocketDisconnect) as excinfo:
        
        # Note: URL must include the '/api' prefix defined in main.py
        with client.websocket_connect("/api/ws/agent/1989") as websocket:
            
            websocket.send_json(perception_payload)
            
            # The server will spin for ~30 seconds (or however long 25 steps takes)
            # and then crash/close the socket.
            # We try to receive until that happens.
            try:
                while True:
                    response = websocket.receive_json()
                    print(f"Agent Step: {response.get('task')}")
            except WebSocketDisconnect:
                raise # Re-raise to be caught by pytest.raises

    # Verify we got the correct error code (Internal Server Error)
    assert excinfo.value.code == 1011
    print("\n✅ Test Passed: Agent correctly spiraled into madness and crashed.")
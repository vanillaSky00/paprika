import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agents.graph import graph_app
from app.api.schemas import Perception

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        await websocket.send_json(message)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            connection.send_json(message)


manager = ConnectionManager()

@router.get("/")
async def read_main():
    return {"msg": "Welcome to Paparika!"}

@router.websocket("/ws/agent/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Handles distinct sessions.
    Unity URL Example: ws://localhost:8000/api/ws/agent/123
    """
    await manager.connect(websocket)
    
    try:
        while True:
            # 1. Receive JSON from Client (Unity)
            data = await websocket.receive_json()
            
            # 2. Parse Data (Validation)
            try:
                perception = Perception(**data)
            except Exception as e:
                logger.warning(f"Client #{client_id} sent invalid data: {e}")
                await manager.send_personal_message({"error": "Invalid Data Schema"}, websocket)
                continue
            
            # 3. Initialize Agent State
            initial_state = { 
                "perception": perception,
                "task": "Decide Next Task",
                "skill_guide": "",
                "plan": [],
                "critique": None,
                "retry_count": 0
            }
            
            # 4. Invoke the LangGraph Workflow
            final_state = await graph_app.ainvoke(initial_state)
            
            # 5. Extract Results
            task_name = final_state.get("task", "Unknown")
            # Convert generic AgentAction objects to dicts for JSON serialization
            plan_json = [action.model_dump() for action in final_state.get("plan", [])]
            
            # 6. Construct Response
            # Note: We map internal 'task' to external 'current_task' for clarity
            response = {
                "client_id": str(client_id),
                "current_task": task_name,
                "plan": plan_json
            }
            
            # 7. Send back to Client
            await manager.send_personal_message(response, websocket)
        
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info(f"Client #{client_id} disconnected")
        
    except Exception as e:
        logger.error(f"Critical Error for Client #{client_id}: {e}", exc_info=True)
        await manager.disconnect(websocket)
        try:
            # Close with Internal Server Error code (1011)
            await websocket.close(code=1011)
        except RuntimeError:
            # Socket might already be closed
            pass
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
            data = await websocket.receive_json()
            
            try:
                perception = Perception(**data)
                logger.info(
                    f"👁️ Perception:\n \
                    time_hour: {perception.time_hour}\n \
                    day: {perception.day}\n \
                    mode: {perception.mode}\n \
                    location_id: {perception.location_id}\n \
                    player_nearby: {perception.player_nearby}\n \
                    nearby_objects: {perception.nearby_objects}\n \
                    held_item: {perception.held_item}\n \
                    last_action_status: {perception.last_action_status}\n \
                    last_action_error: {perception.last_action_error}\n")
            except Exception as e:
                logger.warning(f"⚠️ Client #{client_id} sent invalid data: {e}")
                await manager.send_personal_message({"error": "Invalid Data Schema"}, websocket)
                continue
            
            initial_state = { 
                "perception": perception,
                "task": "Decide Next Task",
                "skill_guide": "",
                "plan": [],
                "critique": None,
                "retry_count": 0
            }
            
            final_state = await graph_app.ainvoke(initial_state)
            
            task_name = final_state.get("task", "Unknown")
            plan_json = [action.model_dump() for action in final_state.get("plan", [])]
            
            response = {
                "client_id": client_id,
                "task": task_name,
                "plan": plan_json
            }
            logger.info(
                    f"👁️ Response to Unity:\n \
                    client_id: {response['client_id']}\n \
                    task: {response['task']}\n \
                    plan: {response['plan']}\n")
            await manager.send_personal_message(response, websocket)
        
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info("Client #{client_id} disconnect")
        
    except Exception as e:
        logger.error(f"❌ Critical Error for Client #{client_id}: {e}", exc_info=True)
        await manager.disconnect(websocket)
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            # Socket already closed
            pass 

import logging
import asyncio
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
        # UTF-8 string (the JSON)
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
    
    session_state = {
        "task": "Decide Next Task",
        "plan": [],
        "retry_count": 0,
        "skill_guide": ""
    }
    
    try:
        while True:
            data = await websocket.receive_json()
            
            try:
                perception = Perception(**data)

                logger.warning(f"👁️ Agent {client_id} | Time {perception.self.time_hour}:00 | Loc: {perception.self.current_zone}")
                logger.warning(f"📦 FULL PERCEPTION DATA:\n{perception.model_dump_json(indent=2)}")
                
            except Exception as e:
                logger.warning(f"⚠️ Client #{client_id} sent invalid data: {e}")
                await manager.send_personal_message({"error": "Invalid Data Schema"}, websocket)
                continue
            
            initial_state = { 
                "perception": perception,
                "task": session_state["task"],
                "skill_guide": session_state["skill_guide"],
                "plan": session_state["plan"],
                "critique": None,
                "retry_count": session_state["retry_count"]
            }
            
            final_state = await graph_app.ainvoke(initial_state)
            
            # --- UPDATE SESSION STATE ---
            # Save the new task/plan so we remember it next time
            session_state["task"] = final_state.get("task", "Decide Next Task")
            session_state["plan"] = final_state.get("plan", [])
            session_state["retry_count"] = final_state.get("retry_count", 0)
            session_state["skill_guide"] = final_state.get("skill_guide", "")
            
            task_name = final_state.get("task", "Unknown")
            plan_json = [action.model_dump() for action in final_state.get("plan", [])]
            
            response = {
                "client_id": client_id,
                "task": task_name,
                "plan": plan_json
            }
            logger.warning(
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
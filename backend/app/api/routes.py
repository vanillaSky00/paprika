import logging
import json
import asyncio
import os
import redis.asyncio as redis
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agents.graph import graph_app
from app.api.schemas import Perception

logger = logging.getLogger(__name__)

router = APIRouter()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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
    # try:
        # Session recover if found
        # session_key = f"session:{client_id}"
        # stored_data = await redis_client.get(session_key)
        
        # if stored_data:
        #     logger.info(f"🔄 RESTORED session for {client_id} from Redis")
        #     session_state = json.loads(stored_data)
            
        #     await manager.send_personal_message({
        #         "type": "RESUMED", 
        #         "task": session_state.get("task", "Unknown"),
        #         "plan": session_state.get("plan", []),
        #         "retry_count": session_state.get("retry_count", 0),
        #         "skill_guide": session_state.get("skill_guide", "")
        #     }, websocket)
            
        # else:
        #     logger.info(f"🆕 NEW session for {client_id}")
        #     session_state = {
        #         "task": "Decide Next Task",
        #         "plan": [],
        #         "retry_count": 0,
        #         "skill_guide": ""
        #     }
    # except Exception as e:
    #     logger.error(f"⚠️ Redis Load Error: {e}. Continuing with in-memory session.")
    
    try:
        while True:
            data = await websocket.receive_json()
            
            try:
                perception = Perception(**data)

                logger.warning(f"👁️ Agent {client_id} | Time {perception.self.time_hour}:00 | Loc: {perception.self.current_zone}")
                
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
            
            # session handle
            session_state["task"] = final_state.get("task", "Decide Next Task")
            session_state["plan"] = final_state.get("plan", [])
            # session_state["plan"] = [a.model_dump() for a in final_state.get("plan", [])]
            session_state["retry_count"] = final_state.get("retry_count", 0)
            session_state["skill_guide"] = final_state.get("skill_guide", "")
            # If the server crashes 1 second later, this data is safe in Redis.
            # try:
            #     await redis_client.set(session_key, json.dumps(session_state))
            # except Exception as e:
            #     logger.error(f"⚠️ Redis Save Failed: {e}")
            
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
        logger.info(f"🔌 Client #{client_id} disconnected. Memory saved in Redis.")
        
    except Exception as e:
        logger.error(f"❌ Critical Error for Client #{client_id}: {e}", exc_info=True)
        await manager.disconnect(websocket)
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            # Socket already closed
            pass 
        
        
        
def _serialize_plan(plan_items: list[Any]) -> list[dict[str, Any]]:
    """
    Safely converts a list of AgentAction objects OR dictionaries into a JSON-serializable list.
    """
    serialized = []
    if not plan_items:
        return []

    for item in plan_items:
        try:
            if hasattr(item, "model_dump"):
                # It's a Pydantic v2 model (AgentAction)
                serialized.append(item.model_dump())
            elif isinstance(item, dict):
                # It's already a dictionary (from memory/previous state)
                serialized.append(item)
            else:
                # Fallback for unexpected types
                logger.warning(f"⚠️ Skipping unserializable plan item: {type(item)}")
        except Exception as e:
            logger.error(f"❌ Serialization error on item: {e}")
            
    return serialized
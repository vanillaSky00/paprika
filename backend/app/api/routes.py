import logging
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.agents.graph import graph_app
from app.api.schemas import Perception
from app.context.view import build_perception_context
from app.core.config import settings
from app.core.exceptions import (
    AgentExecutionError,
    ContextBuildError,
    InvalidPerceptionError,
    PaprikaError,
)

logger = logging.getLogger(__name__)

router = APIRouter()

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


_CLIENT_ERROR_MESSAGES: dict[type[PaprikaError], str] = {
    InvalidPerceptionError: "Invalid perception schema",
    ContextBuildError: "Failed to build perception context",
    AgentExecutionError: "Agent failed to produce a plan",
}


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
            await connection.send_json(message)


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

    # client_id = actor_id is 1:1 When client_id isn't a numeric actor row id, fall back to a
    # stable hash so the graph can still run, row is tracked in the ADR-011 follow-up.
    try:
        actor_id = int(client_id)
    except (TypeError, ValueError):
        actor_id = abs(hash(client_id)) % (2**31)

    session_state: dict[str, Any] = {
        "actor_id": actor_id,
        "task": "Decide Next Task",
        "plan": [],
        "retry_count": 0,
        "skill_guide": "",
        "recent_history": [],
    }

    try:
        while True:
            data = await websocket.receive_json()

            try:
                response = await _process_frame(data, session_state, client_id)
            except PaprikaError as e:
                err_type = type(e).__name__
                client_msg = _CLIENT_ERROR_MESSAGES.get(type(e), "Internal agent error")
                logger.warning("⚠️ %s for client %s: %s", err_type, client_id, e)
                await manager.send_personal_message(
                    {"error": client_msg, "type": err_type}, websocket
                )
                continue

            logger.info(
                "📤 Response → %s | task=%s | plan=%d steps",
                client_id,
                response["task"],
                len(response["plan"]),
            )
            await manager.send_personal_message(response, websocket)

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info("🔌 Client #%s disconnected.", client_id)

    except Exception:
        logger.exception("❌ Critical error for client #%s", client_id)
        await manager.disconnect(websocket)
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            # Socket already closed
            pass


async def _process_frame(
    data: dict,
    session_state: dict[str, Any],
    client_id: str,
) -> dict[str, Any]:
    """
    Run one perception = one plan cycle.
    Raises a `PaprikaError` subclass on any recoverable failure so the
    WebSocket loop can translate it into a structured client response
    without having to know which line blew up.
    """
    try:
        perception = Perception(**data)
    except ValidationError as e:
        raise InvalidPerceptionError(str(e)) from e

    logger.info(
        "Agent %s | Time %d:00 | Loc: %s",
        client_id,
        perception.self.time_hour,
        perception.self.current_zone,
    )
    logger.debug("raw perception payload: %s", data)

    try:
        context = build_perception_context(
            perception=perception,
            retry_count=session_state["retry_count"],
            current_task=session_state["task"],
        )
    except Exception as e:
        raise ContextBuildError(str(e)) from e
    logger.debug("perception context:\n%s", context)

    # Context is built once here and threaded through state. Agent nodes
    # consume state['context'] and must not import app.context.view.
    initial_state = {
        "perception": perception,
        "context": context,
        "actor_id": session_state["actor_id"],
        "task": session_state["task"],
        "skill_guide": session_state["skill_guide"],
        "plan": session_state["plan"],
        "critique": None,
        "retry_count": session_state["retry_count"],
        "recent_history": session_state["recent_history"],
    }

    try:
        final_state = await graph_app.ainvoke(initial_state)
    except Exception as e:
        raise AgentExecutionError(str(e)) from e

    session_state["task"] = final_state.get("task", "Decide Next Task")
    session_state["plan"] = final_state.get("plan", [])
    session_state["retry_count"] = final_state.get("retry_count", 0)
    session_state["skill_guide"] = final_state.get("skill_guide", "")
    session_state["recent_history"] = final_state.get("recent_history", [])

    return {
        "client_id": client_id,
        "task": session_state["task"],
        "plan": _serialize_plan(session_state["plan"]),
    }


def _serialize_plan(plan_items: list[Any]) -> list[dict[str, Any]]:
    """
    Convert AgentAction objects or dicts into a JSON-serializable list.
    """
    serialized: list[dict[str, Any]] = []
    if not plan_items:
        return []

    for item in plan_items:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump())
        elif isinstance(item, dict):
            serialized.append(item)
        else:
            logger.warning("⚠️ Skipping unserializable plan item: %s", type(item))

    return serialized

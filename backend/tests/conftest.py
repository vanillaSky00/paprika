import os
from datetime import datetime

import pytest

from app.api.schemas import (
    AgentAction,
    CreateMemoryDTO,
    GameMode,
    MemoryDTO,
    Perception,
    WorldObject,
)


def pytest_configure(config):
    config.addinivalue_line("markers", "paid: tests that call paid APIs")
    config.addinivalue_line("markers", "integration: hits real external services")


@pytest.fixture(scope="session")
def require_api_key():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("API key not set")


# ------------------------------------------------------------------
# World Objects (Unity-side perception)
# ------------------------------------------------------------------


@pytest.fixture
def dummy_stove():
    return WorldObject(
        id="Stove_01",
        type="Station",
        position={"x": 2.0, "y": 0.0, "z": 4.5},
        distance=2.3,
        state="off",
    )


@pytest.fixture
def dummy_tomato():
    return WorldObject(
        id="Tomato_Clone_5",
        type="Ingredient",
        position={"x": 1.2, "y": 0.0, "z": 3.8},
        distance=1.1,
        state="fresh",
    )


@pytest.fixture
def dummy_plate():
    return WorldObject(
        id="Plate_01",
        type="Prop",
        position={"x": 2.5, "y": 0.0, "z": 4.0},
        distance=2.6,
        state="empty",
    )


@pytest.fixture
def dummy_world_objects(dummy_stove, dummy_tomato, dummy_plate):
    """Convenience bundle for nearby_objects."""
    return [dummy_stove, dummy_tomato, dummy_plate]


# ------------------------------------------------------------------
# Perception (Unity → Backend)
# ------------------------------------------------------------------


@pytest.fixture
def dummy_perception(dummy_world_objects):
    return Perception(
        time_hour=12,
        day=3,
        mode=GameMode.REALITY,
        location_id="Kitchen_A",
        player_nearby=True,
        nearby_objects=dummy_world_objects,
        held_item=None,
        last_action_status="Failed",
        last_action_error="Too far from Stove_01",
    )


# ------------------------------------------------------------------
# Agent Actions (Backend → Unity)
# ------------------------------------------------------------------


@pytest.fixture
def dummy_action_move_to():
    return AgentAction(
        thought_trace="I should move closer to the stove before interacting.",
        tool_name="move_to",
        args={
            "target_id": "Stove_01",
            "stop_distance": 0.8,
        },
        plan_complete=False,
    )


@pytest.fixture
def dummy_action_interact():
    return AgentAction(
        thought_trace="I am close enough to turn on the stove.",
        tool_name="interact",
        args={
            "target_id": "Stove_01",
            "action": "turn_on",
        },
        plan_complete=False,
    )


# ------------------------------------------------------------------
# Memory objects
# ------------------------------------------------------------------


@pytest.fixture
def dummy_create_memory():
    return CreateMemoryDTO(
        day=3,
        time=12,
        mode="reality",
        location_id="Kitchen_A",
        content="Tried to cook but was too far from the stove.",
        memory_type="failure",
        emotion_tags=["confused"],
        importance=0.6,
    )


@pytest.fixture
def dummy_memory():
    return MemoryDTO(
        id=42,
        in_game_day=3,
        time_slot=12,
        mode="reality",
        location_id="Kitchen_A",
        content="Learned I must stand closer to the stove to cook.",
        memory_type="lesson",
        emotion_tags=["focused"],
        importance=0.8,
        created_at=datetime.utcnow(),
    )

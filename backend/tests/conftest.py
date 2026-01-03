import os
import pytest
from datetime import datetime

# Import the new nested schemas
from app.api.schemas import (
    AgentAction,
    CreateMemoryDTO,
    MemoryDTO,
    Perception,
    ObjectView,
    SelfState,
    Sensory,
    TraceStep 
)
from app.config import settings

def pytest_configure(config):
    config.addinivalue_line("markers", "paid: tests that call paid APIs")
    config.addinivalue_line("markers", "integration: hits real external services")

@pytest.fixture(scope="session")
def require_api_key():
    """
    Dependency that forces a skip if the API key is missing or dummy.
    Usage: pass 'require_api_key' as an argument to your test function.
    """
    key = settings.OPENAI_API_KEY
    if not key:
        pytest.skip("OPENAI_API_KEY is not set")
    if key.startswith("dummy") or key == "fake-key":
        pytest.skip("OPENAI_API_KEY is set to a dummy value (skipping live test)")

# --- SHARED SKIP CONDITION (For @pytest.mark.skipif) ---
# We use this boolean in the decorators below
skip_live_tests = (
    not settings.OPENAI_API_KEY or 
    str(settings.OPENAI_API_KEY).startswith("dummy") or 
    settings.OPENAI_API_KEY == "fake-key"
)

# ------------------------------------------------------------------
# World Objects (Unity-side perception)
# ------------------------------------------------------------------

@pytest.fixture
def dummy_stove():
    return ObjectView(
        id="Stove_01",
        type="Station",
        distance=2.3,
        state={"is_on": False, "is_occupied": False}
    )

@pytest.fixture
def dummy_tomato():
    return ObjectView(
        id="Tomato_Clone_5",
        type="Ingredient",
        distance=1.1,
        state={"is_fresh": True}
    )

@pytest.fixture
def dummy_plate():
    return ObjectView(
        id="Plate_01",
        type="Prop",
        distance=2.6,
        state={"is_empty": True}
    )

@pytest.fixture
def dummy_world_objects(dummy_stove, dummy_tomato, dummy_plate):
    return [dummy_stove, dummy_tomato, dummy_plate]

# ------------------------------------------------------------------
# Perception (Unity → Backend)
# ------------------------------------------------------------------

@pytest.fixture
def dummy_perception(dummy_world_objects):
    return Perception(
        self=SelfState(
            time_hour=12,
            current_zone="Kitchen_A",
            held_item=None,
        ),
        sensory=Sensory(
            player_nearby=True,
            visible_objects=dummy_world_objects,
            reachable_objects=[],  # keep explicit if your schema has it
        ),
        statistics={
            "table_item_count": 0,
            "table_items": [],
        },
        execution_trace=[
            TraceStep(
                step_index=1,
                function="move_to",
                id="Stove_01",          # was target_id
                status="failed",
                message="Too far from Stove_01",
            )
        ],
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
from dataclasses import dataclass
from typing import Any
from app.config import Settings

@dataclass
class ToolContext:
    """
    The 'Toolbox' passed to every builder.
    If you add a new global dependency (like Redis), just add it here.
    """
    settings: Settings 
    game_state: Any = None
    db_session: Any = None
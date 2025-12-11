from dataclasses import dataclass
from typing import Any

@dataclass
class ToolContext:
    """
    The 'Toolbox' passed to every builder.
    If you add a new global dependency (like Redis), just add it here.
    """
    settings: Any
    game_state: Any = None
    db_session: Any = None
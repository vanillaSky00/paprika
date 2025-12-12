from app.tools.base import tool_registry
from app.tools.context import ToolContext

# Explicit import:
# We import the sub-packages. This triggers their __init__.py,
# which imports their files, which runs the decorators.
import app.tools.external
import app.tools.internal

def load_global_tools(settings, game_state=None) -> list:
    """
    Called by deps.py. 
    Because we imported 'external' and 'internal' above,
    the registry is already populated.
    """
    ctx = ToolContext(settings=settings, game_state=game_state)
    return tool_registry.build_all(ctx)
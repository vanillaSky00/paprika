from typing import List, Optional, TypedDict

from app.api.schemas import AgentAction, MemoryDTO, Perception


class AgentState(TypedDict):
    """
    Input from unity -> fetch memory with postgres -> make decision
    """

    perception: Perception

    memories: List[MemoryDTO]

    final_action: Optional[AgentAction]

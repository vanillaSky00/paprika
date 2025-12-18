from backend.app.prompts.prompts import DREAM_SYSTEM_PROMPT, REALITY_SYSTEM_PROMPT

from app.agents.state import AgentState
from app.api.schemas import AgentAction, GameMode
from app.llm.base import BaseLLMClient


async def decide_action(state: AgentState, llm: BaseLLMClient) -> AgentState:
    perception = state["perception"]
    memories = state["memories"]

    if perception.mode == GameMode.DREAM:
        sys_prompt = DREAM_SYSTEM_PROMPT
    else:
        sys_prompt = REALITY_SYSTEM_PROMPT

    memory_text = "\n".join([f"- {m.content}" for m in memories])

    user_msg = f"""
    Loaction: {perception.location_id}
    Events: {perception.recent_events}
    Memories:
    {memory_text}
    """

    action = await llm.generate_structured(sys_prompt, user_msg, AgentAction)

    return {"final_action": action}

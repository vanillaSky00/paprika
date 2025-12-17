import operator
import logging
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

from app.agents.curriculum import CurriculumAgent
from app.agents.skill import SkillAgent
from app.agents.action import ActionAgent
from app.agents.critic import CriticAgent
from app.memory.pgvector_repo import PostgresMemoryStore
from app.deps import get_llm, get_session_factory
from app.tools.base import tool_registry
from app.tools.context import ToolContext
from app.config import settings 
from app.api.schemas import Perception, AgentAction, CriticOutput

logger = logging.getLogger(__name__)

llm = get_llm("openai", "gpt-4.1-mini")

session_factory = get_session_factory()
memory_store = PostgresMemoryStore(session_factory)

tool_context = ToolContext(
    settings=settings,
    db_session=session_factory
)
tools = tool_registry.build_all(tool_context)

curriculum_agent = CurriculumAgent(
    llm=llm,
    qa_llm=llm,
    memory_store=memory_store
)

skill_agent = SkillAgent(
    llm=llm,
    memory_store=memory_store,
)

action_agent = ActionAgent(
    llm=llm,
    tools=tools
)

critic_agent = CriticAgent(
    llm=llm
)


class AgentState(TypedDict):
    perception: Perception
    
    task: str
    skill_guide: str
    plan: list[AgentAction]
    critique: CriticOutput | None
    
    retry_count: int
    
    
async def curriculum_node(state: AgentState):
    logger.info("--- 🧠 CURRICULUM: Thinking... ---")
    
    proposal = await curriculum_agent.propose_next_task(state['perception'])
    
    return {
        "task": proposal.task,
        "skill_guide" : "",
        "retry_count": 0,
        "plan": [],
        "critique": None,
    }


async def skill_node(state: AgentState):
    logger.info(f"--- 📚 SKILL: Researching '{state['task']}'... ---")
    
    guide = await skill_agent.retrieve_skill(state['task'])
    
    return {
        "skill_guide": guide
    }


async def action_node(state: AgentState):
    logger.info("--- 🚀 ACTION: Planning... ---")
    
    last_plan = [a.model_dump() for a in state['plan']] if state['plan'] else ""
    critic_text = state['critique'].feedback if state['critique'] else ""
    
    plan = await action_agent.generate_plan(
        perception=state['perception'],
        current_task=state['task'],
        last_plan=last_plan,
        critique=critic_text
    )
    
    return {
        "plan": plan
    }
    

async def critic_node(state: AgentState):
    logger.info("--- 🧐 CRITIC: Judging... ---")
    
    critique = await critic_agent.check_task_success(
        perception=state['perception'],
        current_task=state['task']
    )
    
    return {
        "critique": critique,
        "retry_count": state['retry_count'] + 1
    }


async def learning_node(state: AgentState):
    logger.info("--- 🎓 LEARNING: Saving to Long-Term Memory... ---")
    
    action_history_dicts = [a.model_dump() for a in state['plan']]
    
    await skill_agent.learn_new_skill(
        task=state['task'],
        action_history=action_history_dicts,
        success=True,
    )
    
    return {}


def decide_next_node(state: AgentState):
    """
    Why: This ensure the deterministic based on given state
    """
    critique = state['critique']
    
    if critique.success:
        return "learning"
    
    elif state['retry_count'] <= 3:
        logger.warning(f"⚠️ Failed. Retrying ({state['retry_count']}/3)...")
        return "action"
    
    else:
        logger.error("❌ Too many failures. Giving up.")
        return "curriculum"


workflow = StateGraph(ActionAgent)

workflow.add_node("curriculum", curriculum_node)
workflow.add_node("skill", skill_node)
workflow.add_node("action", action_node)
workflow.add_node("critic", critic_node)
workflow.add_node("learning", learning_node)

workflow.set_entry_point("curriculum")

workflow.add_edge("curriculum", "skill")
workflow.add_edge("skill", "action")
workflow.add_edge("action", "critic")

workflow.add_conditional_edges(
    "critic",
    decide_next_node,
    {
        "learning": "learning",
        "action": "action",
        "curriculum": "curriculum"
    }
)

workflow.add_edge("learning", "curriculum")

graph_app = workflow.compile()
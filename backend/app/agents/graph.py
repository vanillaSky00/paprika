import logging
from typing import TypedDict
from langgraph.graph import END, StateGraph

from app.agents.action import ActionAgent
from app.agents.critic import CriticAgent
from app.agents.curriculum import CurriculumAgent
from app.agents.skill import SkillAgent
from app.api.schemas import AgentAction, CriticOutput, Perception
from app.core.config import settings
from app.core.db import get_session_factory
from app.core.deps import get_llm, get_memory_store
from app.tools.base import tool_registry
from app.tools.context import ToolContext

logger = logging.getLogger(__name__)

openai_llm = get_llm("openai", "gpt-4.1-mini")

session_factory = get_session_factory()
memory_store = get_memory_store()

tool_context = ToolContext(
    settings=settings,
    db_session=session_factory
)
tools = tool_registry.build_all(tool_context)

curriculum_agent = CurriculumAgent(
    llm=openai_llm,
    qa_llm=openai_llm,
    memory_store=memory_store
)

skill_agent = SkillAgent(
    llm=openai_llm,
    memory_store=memory_store,
)

action_agent = ActionAgent(
    llm=openai_llm,
    tools=tools
)

critic_agent = CriticAgent(
    llm=openai_llm
)


class AgentState(TypedDict):
    perception: Perception
    context: str

    # Identifies which actor (NPC/human row in `actors`) this invocation
    # speaks for. Threaded into every memory call so RAG retrieval and
    # skill lookups stay scoped to the right mind. Required.
    actor_id: int

    task: str
    skill_guide: str
    plan: list[AgentAction]
    critique: CriticOutput | None

    # Rolling task-level outcomes (Success/Failed). Was an attribute on
    # CurriculumAgent — moved into state so the agent stays a stateless
    # service that can be shared across actors.
    recent_history: list[dict]

    retry_count: int


# Trim length for `recent_history` — keeps the curriculum prompt bounded.
_HISTORY_WINDOW = 10


async def curriculum_node(state: AgentState):
    logger.info("--- 🧠 CURRICULUM: Thinking... ---")

    proposal = await curriculum_agent.propose_next_task(
        context=state['context'],
        actor_id=state['actor_id'],
        recent_history=state.get('recent_history', []),
    )

    return {
        "task": proposal.task,
        "skill_guide": "",
        "retry_count": 0,
        "plan": [],
        "critique": None,
    }


async def skill_node(state: AgentState):
    logger.info(f"--- 📚 SKILL: Researching '{state['task']}'... ---")

    guide = await skill_agent.retrieve_skill(
        task=state['task'],
        actor_id=state['actor_id'],
    )

    return {
        "skill_guide": guide
    }


async def action_node(state: AgentState):
    logger.info("--- 🚀 ACTION: Planning... ---")

    last_plan = [a.model_dump() for a in state['plan']] if state['plan'] else ""
    critic_text = state['critique'].feedback if state['critique'] else ""
    skill_guide = state.get("skill_guide", "")

    plan = await action_agent.generate_plan(
        context=state['context'],
        current_task=state['task'],
        skill_guide=skill_guide,
        last_plan=last_plan,
        critique=critic_text,
    )

    return {
        "plan": plan
    }


async def critic_node(state: AgentState):
    logger.info("--- 🧐 CRITIC: Judging... ---")

    critique = await critic_agent.check_task_success(
        context=state['context'],
        current_task=state['task'],
    )

    return {
        "critique": critique,
        "retry_count": state['retry_count'] + 1
    }

async def failure_node(state: AgentState):
    logger.warning(f"--- 💀 FAILURE: Giving up on '{state['task']}' ---")

    history = state.get('recent_history', []) + [
        {"task": state['task'], "result": "Failed"}
    ]

    return {
        "plan": [],
        "retry_count": 0,
        "critique": None,
        "recent_history": history[-_HISTORY_WINDOW:],
    }

async def learning_node(state: AgentState):
    logger.info("--- 🎓 LEARNING: Saving to Long-Term Memory... ---")

    action_history_dicts = [a.model_dump() for a in state['plan']]

    await skill_agent.learn_new_skill(
        task=state['task'],
        action_history=action_history_dicts,
        success=True,
        actor_id=state['actor_id'],
    )

    history = state.get('recent_history', []) + [
        {"task": state['task'], "result": "Success"}
    ]

    return {
        "recent_history": history[-_HISTORY_WINDOW:],
    }

def entry_router(state: AgentState):
    """
    Decide where to start based on if this is "first run" or not from unity?
    """

    current_task = state.get("task", "")

    if not current_task or current_task == "Decide Next Task":
        return "curriculum"

    return "critic"

def decide_next_node(state: AgentState):
    """
    Why: This ensure the deterministic based on given state
    """
    critique = state['critique']

    if critique.success:
        return "learning"

    elif state['retry_count'] <= 2:
        logger.warning(f"⚠️ Failed. Retrying ({state['retry_count']}/2)...")
        return "action"

    else:
        logger.error("❌ Too many failures. Giving up.")
        return "failure"

def build_graph():
    workflow = StateGraph(AgentState)

    workflow.add_node("curriculum", curriculum_node)
    workflow.add_node("skill", skill_node)
    workflow.add_node("action", action_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("learning", learning_node)


    workflow.set_conditional_entry_point(
        entry_router,
        {
            "curriculum": "curriculum",
            "critic": "critic"
        }
    )

    workflow.add_edge("curriculum", "skill")
    workflow.add_edge("skill", "action")
    workflow.add_node("failure", failure_node)

    # Action goes to END (stops Python), so Unity can run the plan.
    workflow.add_edge("action", END)

    workflow.add_conditional_edges(
        "critic",
        decide_next_node,
        {
            "learning": "learning",
            "action": "action",
            "failure": "failure"
        }
    )
    workflow.add_edge("failure", "curriculum") # <--- Loop back to try a NEW task
    workflow.add_edge("learning", "curriculum")

    return workflow.compile()


# Compiled once at import; shared across all actors. See ADR-013.
graph_app = build_graph()

from langgraph.graph import END, StateGraph

from app.agents.nodes.decide import decide_action
from app.agents.state import AgentState
from app.deps import get_llm


async def run_decide(state: AgentState):
    llm = get_llm()
    return await decide_action(state, llm)


builder = StateGraph(AgentState)
builder.add_node("brain", run_decide)
builder.set_entry_point("brain")
builder.add_edge("brain", END)

agent_graph = builder.compile()

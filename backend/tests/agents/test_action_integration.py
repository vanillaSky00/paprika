from app.agents.action import ActionAgent
from app.tools import load_global_tools
from app.deps import get_default_llm
from app.config import settings
from app.tools import load_global_tools

def test_action_integration_prompt_rendering(dummy_perception):
    llm = get_default_llm()
    tools = load_global_tools(settings=settings)
    agent = ActionAgent(llm, tools)

    print("TOOLS LEN =", len(tools))
    print("TOOLS =", [getattr(t, "name", type(t).__name__) for t in tools])
    
    system_msg = agent.render_system_message()
    human_msg = agent.render_human_message(perception=dummy_perception, current_task="demo")

    print(system_msg)
    print(human_msg)

    # Assert directly on message content (better than captured output)
    assert system_msg is not None
    assert human_msg is not None
    assert "Kitchen_A" in human_msg.content
    assert "Stove_01" in human_msg.content

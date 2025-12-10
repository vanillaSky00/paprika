import asyncio
from app.agent.graph import agent_graph
from app.agent.state import AgentState
from app.api.schemas import Perception, GameMode, AgentActionType

async def main():
    print("Simulating Unity Input...")
    dummy_perception = Perception(
        time_hour=22,
        day=1,
        mode=GameMode.DREAM,
        location_id="bedroom",
        player_nearby=None,
        recent_events=["quiet_humming", "lights_flickering"]
    )
    
    initial_state: AgentState = {
        "perception": dummy_perception,
        "memories": [],
        "final_action": None
    }
    
    result = await agent_graph.ainvoke(initial_state)
    action = result["final_action"]
    
    if not action:
        print("Error: No action returned.")
        return

    # 4. Check Result (Using Enum)
    print(f"\nAI Decision: {action.action_type}")
    print(f"Thought: {action.thought_trace}")

    # <--- STRICT ENUM CHECK
    if action.action_type == AgentActionType.SAY:
        print(f"Text: {action.text}")
    
    elif action.action_type == AgentActionType.MOVE:
        print(f"Target: {action.target_location}")

    elif action.action_type == AgentActionType.SPAWN:
        print(f"Spawning: {action.spawn}")

if __name__ == "__main__":
    asyncio.run(main())
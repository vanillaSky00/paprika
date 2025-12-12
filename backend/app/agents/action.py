import json
from langchain_core.tools import StructuredTool
from langchain_core.messages import SystemMessage, HumanMessage
from app.llm.base import BaseLLMClient
from app.api.schemas import Perception, AgentAction
from app.prompts import loader as ld

class ActionAgent:
    def __init__(self,
                 llm: BaseLLMClient,
                 tools: list[StructuredTool] | None,
                 template_name: str = "system_main",
                 ):
        self.llm = llm
        self.system_prompts = ld.build_system_prompt(template_name, tools)
    
    def render_system_message(self):
        return SystemMessage(content=self.system_prompts)
    
    def render_human_message(
        self,
        *,
        perception: Perception,
        current_task,
        last_plan="",
        critique="",
    ):
        """
        The eyes of LLM: the 'Context' construction, tell llm what happened
        """

        # Normalize Perception → dict
        p = perception.model_dump()

        visuals = ""
        if p.get("nearby_objects"):
            obj_list = [
                f"{o['id']} ({o.get('state', 'default')})"
                for o in p["nearby_objects"]
            ]
            visuals = f"I can see: {', '.join(obj_list)}"
        else:
            visuals = "I see nothing interactable nearby"

        status = f"""
        Time: {p['time_hour']},
        Location: {p['location_id']},
        Holding: {p['held_item']}
        """

        task_context = f"""
        Current Goal: {current_task}
        """

        feedback = ""
        if last_plan:
            if critique:
                feedback = f"""
                --- ❌ PREVIOUS PLAN FAILED ---
                Your last attempt: {json.dumps(last_plan)}
                Error from Engine: {critique}
                (Critique: You cannot do that action right now. Try a different tool.)
                """
            else:
                feedback = f"""
                --- ✅ PREVIOUS PLAN SUCCESS ---
                Last action succeeded. Continue to the next step.
                """

        content = f"""
        --- OBSERVATION ---
        {status.strip()}
        {visuals}
        {last_plan}
        --- TASK ---
        {task_context.strip()}

        {feedback}

        Based on this, what is the next step?
        """

        return HumanMessage(content=content)

    def generate_plan(self):
        """
        The Main Loop: Context -> LLM -> JSON
        """
        sys_msg = self.render_system_message()
        
        pass
    
    def _process_response(self, content: str) -> list[AgentAction]:
        """
        Parses the LLM output, expect JSON.
        """
        pass
    

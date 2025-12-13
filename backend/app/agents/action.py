import json
import logging

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from app.api.schemas import AgentAction, Perception
from app.llm.base import BaseLLMClient
from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class ActionAgent(BaseAgent):
    def __init__(
        self, 
        llm: BaseLLMClient,
        template_name="action",
        tools: list[StructuredTool] | None = None, 
    ):
        super().__init__(llm, template_name, tools)

    def render_human_message(
        self,
        *,
        perception: Perception,
        current_task,
        last_plan="",
        critique="",
    ) -> HumanMessage:
        """
        The eyes of LLM: the 'Context' construction, tell llm what happened
        """

        items = [f"{o.id}({o.state})" for o in perception.nearby_objects]

        if items:
            visuals = f"I can see: {', '.join(items)}"
        else:
            visuals = "I see nothing interactable nearby"

        # Make status
        content = f"""
        --- OBSERVATION ---
        Time: {perception.time_hour}:00
        Location: {perception.location_id}
        Holding: {perception.held_item or "Nothing"}
        Visible: {visuals}

        --- TASK ---
        Current Goal: {current_task}
        """

        # Voyager Feedback Loop
        if last_plan and critique:
            content += f"""
            --- PREVIOUS FAILURE ---
            Your last plan failed.
            Plan: {json.dumps(last_plan)}
            Error/Critique: {critique}
            
            ADVICE: Use a different tool or check your arguments.
            """

        return HumanMessage(content=content)

    async def generate_plan(
        self,
        *,
        perception: Perception,
        current_task,
        last_plan="",
        critique="",
    ) -> list[AgentAction]:
        """
        The Main Loop: Context -> LLM -> JSON
        """
        response_text = await self.llm.generate_response(
            system_prompt=self.render_system_message().content,
            user_message=self.render_human_message(
                perception=perception,
                current_task=current_task,
                last_plan=last_plan,
                critique=critique,
            ).content,
        )

        logger.info(f"\n\n[LLM response]:{response_text}\n")

        return self._generate_plan_helper(response_text)

    def _generate_plan_helper(self, content: str) -> list[AgentAction]:
        """
        Validates raw JSON into AgentAction objects.
        """
        data = self._parse_json_helper(content)

        if not data:
            return []
        
        if isinstance(data, dict):
            data = [data]
            
        valid_actions = []
        for i, item in enumerate(data):
            try:
                # Can add customized error handle if llm use other key in dict rather than 'function'
                action = AgentAction(**item)
                valid_actions.append(action)

            except Exception as e:
                logger.warning(f"Skipping invalid action at index {i}: {e}")
                continue

        return valid_actions

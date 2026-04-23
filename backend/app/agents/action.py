import json
import logging

from langchain_core.messages import HumanMessage
from langchain_core.tools import StructuredTool

from app.agents.base import BaseAgent
from app.api.schemas import AgentAction
from app.llm.base import BaseLLMClient

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
        context: str,
        current_task: str,
        skill_guide: str = "",
        last_plan: str = "",
        critique: str = "",
    ) -> HumanMessage:
        """
        This method only layers Action-specific sections on top:
          - the current task
          - an optional retrieved skill (cold vs. warm start)
          - Voyager-style critique + last plan on retry
        """
        content = (
            "--- TASK ---\n"
            f"Current Goal: {current_task}\n\n"
            "--- PERCEPTION ---\n"
            f"{context}"
        )

        # Cold(1st) vs. Warm(2nd+) start. ActionAgent can improvise without
        # a stored skill, but follows the guide when it matches.
        if skill_guide:
            content += (
                "\n\n--- SUGGESTED PROCEDURE (MEMORY) ---\n"
                "I have done this task before. Here is the guide:\n"
                f"{skill_guide}\n"
                "INSTRUCTION: Follow the guide if it matches the current situation."
            )

        # Voyager feedback loop.
        if last_plan and critique:
            content += (
                "\n\n--- PREVIOUS FAILURE ---\n"
                "Your last plan failed.\n"
                f"Plan: {json.dumps(last_plan)}\n"
                f"Error/Critique: {critique}\n"
                "ADVICE: Use a different tool or check your arguments."
            )

        return HumanMessage(content=content)

    async def generate_plan(
        self,
        *,
        context: str,
        current_task: str,
        skill_guide: str = "",
        last_plan: str = "",
        critique: str = "",
    ) -> list[AgentAction]:
        
        response_text = await self.llm.generate_response(
            system_prompt=self.render_system_message().content,
            user_message=self.render_human_message(
                context=context,
                current_task=current_task,
                skill_guide=skill_guide,
                last_plan=last_plan,
                critique=critique,
            ).content,
        )

        logger.info("\n\n[Action Agent response]:%s\n", response_text)

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
                action = AgentAction(**item)
                valid_actions.append(action)
            except Exception as e:
                logger.warning("Skipping invalid action at index %d: %s", i, e)
                continue

        return valid_actions

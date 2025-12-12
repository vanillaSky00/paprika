import json
import logging
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool

from app.api.schemas import AgentAction, Perception
from app.llm.base import BaseLLMClient
from app.prompts import loader as ld

logger = logging.getLogger(__name__)


class ActionAgent:
    def __init__(
        self,
        llm: BaseLLMClient,
        tools: list[StructuredTool] | None,
        template_name: str = "system_main",
    ):
        self.llm = llm
        self.tools = tools or []
        self.system_prompts = ld.build_system_prompt(template_name, tools)

    def render_system_message(self) -> SystemMessage:
        return SystemMessage(content=self.system_prompts)

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

        # Normalize Perception → dict
        p = perception.model_dump()

        visuals = ""
        if p.get("nearby_objects"):
            obj_list = [
                f"{o['id']} ({o.get('state', 'default')})" for o in p["nearby_objects"]
            ]
            visuals = f"I can see: {', '.join(obj_list)}"
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

        return self._parse_response(response_text)

    def _parse_response(self, content: str) -> list[AgentAction]:
        """
        Parses the LLM output, expect JSON.
        """
        try:
            # Find a JSON list [...] spanning multiple lines
            match = re.search(r"\[.*\]", content, re.DOTALL)

            if match:
                json_str = match.group(0)
            else:
                # Fallback: Maybe it returned a single object {...} instead of a list
                match_single = re.search(r"\{.*\}", content, re.DOTALL)
                if match_single:
                    json_str = f"{[match_single.group(0)]}"
                else:
                    logger.warning(
                        f"No JSON structure found in response: {content[:100]}..."
                    )
                    return []

            data = json.loads(json_str)

            validate_action = []
            for i, item in enumerate(data):
                try:
                    # Can add customized error handle if llm use other key in dict rather than 'function'
                    action = AgentAction(**item)
                    validate_action.append(action)

                except Exception as e:
                    logger.warning(f"Skipping invalid action at index {i}: {e}")
                    continue

            return validate_action

        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Failed: {e}", extra={"content": content})
            return []

        except Exception as e:
            logger.exception("Unexpected error during parsing")
            return []

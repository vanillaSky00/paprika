import logging

from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent
from app.api.schemas import CriticOutput
from app.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseLLMClient,
        template_name="critic",
        tools=None,
        mode="auto",
    ):
        super().__init__(llm, template_name, tools)
        self.mode = mode

    def render_human_message(
        self,
        context: str,
        current_task: str,
    ) -> HumanMessage:
        """
        Judge GOAL (task) vs. RESULT (current perception).
        """
        content = (
            "--- GOAL ---\n"
            f"{current_task}\n\n"
            "--- PERCEPTION ---\n"
            f"{context}"
        )
        return HumanMessage(content=content)

    # Check entry point, act as router
    async def check_task_success(
        self,
        context: str,
        current_task: str,
        max_retries: int = 3,
    ):
        sys_msg_content = self.render_system_message().content
        human_msg_content = self.render_human_message(context, current_task).content

        if self.mode == "auto":
            return await self.__ai_check_task_success(
                sys_msg_content,
                human_msg_content,
                max_retries,
            )
        elif self.mode == "manual":
            return self.__human_check_task_success()
        else:
            raise ValueError(f"Invalid mode: {self.mode}")

    async def __ai_check_task_success(
        self,
        sys_msg,
        human_msg,
        max_retries,
        last_error: str = "",
        last_raw_response: str = "",
    ) -> CriticOutput:
        if max_retries == 0:
            logger.error("Failed to parse Critic Agent response. Max retries reached.")
            return CriticOutput(
                success=False,
                reasoning="Max retries",
                feedback="System Error",
            )

        # Inject the previous failure into the retry prompt. Without this
        # the same sys_msg/human_msg produces the same malformed output
        # and every retry burns identically.
        effective_human_msg = human_msg
        if last_error:
            effective_human_msg = (
                f"{human_msg}\n\n"
                "--- PREVIOUS ATTEMPT FAILED TO PARSE ---\n"
                f"Your previous response (truncated):\n{last_raw_response[:500]}\n\n"
                f"Parser error: {last_error}\n"
                "Return ONLY a raw JSON object matching the schema — "
                "no code fences, no prose before or after, no trailing commas."
            )

        raw_response = ""
        try:
            raw_response = await self.llm.generate_response(
                system_prompt=sys_msg,
                user_message=effective_human_msg,
            )

            logger.info("\n\n[[Critic Agent response]]:%s\n", raw_response)

            data = self._parse_json_helper(raw_response)

            if not data:
                raise ValueError("No JSON found")
            if isinstance(data, list):
                data = data[0]

            return CriticOutput(**data)

        except Exception as e:
            logger.warning(
                "Error parsing critic response: %s. Retrying (%d left)...",
                e,
                max_retries,
            )
            return await self.__ai_check_task_success(
                sys_msg,
                human_msg,
                max_retries=max_retries - 1,
                last_error=str(e),
                last_raw_response=raw_response,
            )

    # for dev
    def __human_check_task_success(self):
        logger.info("\n--- HUMAN CRITIC MODE ---")

        while True:
            success_input = input("Success? (y/n): ").strip().lower()
            if success_input in ["y", "n"]:
                break

        is_success = success_input == "y"
        reasoning = input("Reasoning: ").strip()
        feedback = input("Feedback: ").strip()

        return CriticOutput(
            success=is_success,
            reasoning=reasoning,
            feedback=feedback,
        )

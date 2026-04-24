import logging

from langchain_core.messages import HumanMessage

from app.agents.base import BaseAgent
from app.api.schemas import CurriculumOutput, MemoryDTO
from app.llm.base import BaseLLMClient
from app.memory.base import BaseMemoryStore

logger = logging.getLogger(__name__)


class CurriculumAgent(BaseAgent):
    def __init__(
        self,
        llm: BaseLLMClient,
        qa_llm: BaseLLMClient,
        memory_store: BaseMemoryStore,
        memory_window_size: int = 10,
        template_name="curriculum",
        tools=None,
        mode="auto",
    ):
        super().__init__(llm, template_name, tools)
        self.qa_llm = qa_llm
        self.memory = memory_store
        self.memory_window_size = memory_window_size
        self.recent_history = []  # {'task': str, 'result': str}
        self.mode = mode

    def render_human_message(
        self,
        context: str,
        long_term_memories: list[MemoryDTO],
    ) -> HumanMessage:
        """
        Curriculum-specific sections:
          - long-term RAG memories (episodic recall)
          - recent task-level history (Success/Failed outcomes — distinct
            from the execution-trace history inside the perception block)
        """
        
        if long_term_memories:
            long_term_memories_str = "\n".join(
                f"- {m.content} (Day {m.in_game_day})" for m in long_term_memories
            )
        else:
            long_term_memories_str = "No relavent memories found."

        if self.recent_history:
            history_str = "\n".join(
                f"- {item['task']} ({item['result']})"
                for item in self.recent_history[-5:]
            )
        else:
            history_str = "None"

        content = (
            "--- PERCEPTION ---\n"
            f"{context}\n\n"
            "--- RELEVANT MEMORIES (What I learned here before) ---\n"
            f"{long_term_memories_str}\n\n"
            "--- RECENT ACTION HISTORY (Do not repeat failed tasks) ---\n"
            f"{history_str}\n\n"
            "Based on my past memories and current state, what is the best next task?"
        )

        return HumanMessage(content=content)

    async def propose_next_task(
        self,
        context: str,
    ) -> CurriculumOutput:

        # TODO: hard code check some basic status (Hunger, etc.)

        relavent_memory = await self.memory.fetch_similar(
            query=context, limit=self.memory_window_size
        )
        sys_msg = self.render_system_message().content
        human_msg = self.render_human_message(context, relavent_memory).content

        if self.mode == "auto":
            return await self.__propose_next_ai_task(sys_msg, human_msg)
        elif self.mode == "manual":
            return self.__propose_next_manual_task()
        else:
            raise ValueError(f"Invalid curriculum agent mode: {self.mode}")

    def add_history(self, task: str, result: str):
        """Records both Success and Failure"""
        self.recent_history.append({"task": task, "result": result})
        if len(self.recent_history) > self.memory_window_size:
            self.recent_history.pop(0)

    async def __propose_next_ai_task(
        self,
        sys_msg,
        human_msg,
        max_retries: int = 3,
        last_error: str = "",
        last_raw_response: str = "",
    ):
        if max_retries == 0:
            # Fallback must be a concrete, verifiable pipeline. A vague
            # "Explore the area" task cascades badly: action emits bare
            # move_to steps, critic accepts them (the world matched the
            # vague intent), and the agent visibly wanders. PLATE_SETUP
            # is the safest default — it's the first phase of every
            # burger and always productive regardless of kitchen state.
            logger.error("Max retries reached. Falling back to PLATE_SETUP.")
            return CurriculumOutput(
                task="Set up the assembly plate on Preparation1",
                reasoning="Curriculum parse failed; defaulting to plate setup so the burger can start.",
                difficulty=1,
            )

        # On retry, tell the model exactly what went wrong last time.
        # Without this, identical input produces identical malformed
        # output, and all 3 retries burn on the same mistake.
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

            logger.info("\n\n[Curriculum Agent response]:%s\n", raw_response)

            data = self._parse_json_helper(raw_response)

            if not data:
                raise ValueError("No JSON found")
            if isinstance(data, list):
                data = data[0]

            return CurriculumOutput(**data)

        except Exception as e:
            logger.warning("Parsing failed: %s. Retrying (%d left)", e, max_retries)
            return await self.__propose_next_ai_task(
                sys_msg,
                human_msg,
                max_retries - 1,
                last_error=str(e),
                last_raw_response=raw_response,
            )

    def __propose_next_manual_task(self):
        task = input("Enter Task: ").strip()
        reasoning = input("Enter Reasoning: ").strip()
        difficulty = input("Enter Difficulty: ").strip()
        return CurriculumOutput(
            task=task,
            reasoning=reasoning,
            difficulty=int(difficulty),
        )

    # TODO handle short-term and long-term add/ delete
    async def record_outcome(self):
        pass

    # TODO handle qa system
    def run_qa(self):
        # self.qa_llm.generate_response()
        pass

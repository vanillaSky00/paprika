import logging
from langchain_core.messages import HumanMessage
from app.api.schemas import Perception, CurriculumOutput, MemoryDTO
from app.memory.base import BaseMemoryStore
from app.llm.base import BaseLLMClient
from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class CurriculumAgent(BaseAgent):
    def __init__(
        self, 
        llm: BaseLLMClient, 
        qa_llm: BaseLLMClient,
        memory_store: BaseMemoryStore,
        memory_window_size: int=5,
        template_name="curriculum", 
        tools=None,
        mode="auto",
    ):
        super().__init__(llm, template_name, tools)
        self.qa_llm = qa_llm
        self.memory = memory_store
        self.memory_window_size = memory_window_size
        self.recent_tasks = [] # short-term buffer (last 5 task)
        self.mode = mode

    def render_human_message(        
        self,
        perception: Perception,
        long_term_memories: list[MemoryDTO]
    ) -> HumanMessage:
        
        if long_term_memories:
            long_term_memories_str = "\n".join([f"- {m.content} (Day {m.in_game_day})" for m in long_term_memories])
        else:
            long_term_memories_str = "No relavent memories found."
        
        short_term_memories_str = ", ".join(self.recent_tasks[-5:]) or "None"
        
        content = f"""
        --- CURRENT STATE ---
        Location: {perception.location_id}
        Inventory: {perception.held_item or "Empty"}
        Status: Day {perception.day}, {perception.time_hour}:00

        --- RELEVANT MEMORIES (What I learned here before) ---
        {long_term_memories_str}

        --- RECENT ACTION HISTORY ---
        {short_term_memories_str}

        Based on my past memories and current state, what is the best next task?
        """
        
        return HumanMessage(content=content)
        
    async def propose_next_task(
        self,
        perception: Perception
    )-> CurriculumOutput:
        """
        Heuristic + RAG Decision Loop
        """
        # TODO: hard code check some basic status (Hunger, etc.)
        
        
        # RAG
        query = (
            f"Location: {perception.location_id}. "
            f"Nearby: {', '.join([o.id for o in perception.nearby_objects])}. "
            f"Holding: {perception.held_item}. "
        ) 
        
        relavent_memory = await self.memory.fetch_similar(query=query, limit=self.memory_window_size)
        sys_msg = self.render_system_message().content
        human_msg = self.render_human_message(perception, relavent_memory).content
        
        if self.mode == "auto":
            return await self.__propose_next_ai_task(
                sys_msg,
                human_msg
            )
        elif self.mode == "manual":
            return self.__propose_next_manual_task()
        else:
            raise ValueError(f"Invalid curriculum agent mode: {self.mode}")
    
    
    async def __propose_next_ai_task(
        self,
        sys_msg,
        human_msg,
        max_retries=5
    ):
        if max_retries == 0:
            logger.error("Max retries reached. Returning Fallback.")
            return CurriculumOutput(
                task="Explore the area",
                reasoning="I failed to think of a task, so I will just wander.",
                difficulty=1
            )
        
        try: 
            curriculum_resp = await self.llm.generate_response(
                system_prompt=sys_msg,
                user_message=human_msg
            )
            
            print(f"\n\n[Curriculum Agent response]:{curriculum_resp}\n")
            logger.info(f"\n\n[Curriculum Agent response]:{curriculum_resp}\n")
            
            data = self._parse_json_helper(curriculum_resp)
            
            if not data:
                raise ValueError("No JSON found")
            if isinstance(data, list):
                data = data[0]
                
            return CurriculumOutput(**data)
        
        except Exception as e:
            logger.warning(f"Parsing failed: {e}. Retrying ({max_retries} left")
            return await self.__propose_next_ai_task(
                sys_msg,
                human_msg,
                max_retries - 1
            )
    
    def __propose_next_manual_task():
        print("--- MANUAL TASK INPUT ---")
        task = input("Enter Task: ").strip()
        reasoning = input("Enter Reasoning: ").strip()
        difficulty = input("Enter Difficulty: ").strip()
        return CurriculumOutput(
            task=task, 
            reasoning=reasoning, 
            difficulty=int(difficulty)
        )
    
    #TODO handle short-term and long-term add/ delete
    async def record_outcome():
        pass
    
    #TODO handle qa system
    def run_qa():
        pass
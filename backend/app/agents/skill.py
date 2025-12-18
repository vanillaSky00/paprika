import logging
from langchain_core.messages import HumanMessage
from app.agents.base import BaseAgent
from app.llm.base import BaseLLMClient
from app.memory.base import BaseMemoryStore
from app.api.schemas import SkillDTO

logger = logging.getLogger(__name__)


class SkillAgent(BaseAgent):
    def __init__(
        self, 
        llm: BaseLLMClient, 
        memory_store: BaseMemoryStore,
        template_name="skill", 
        tools=None,
    ):
        super().__init__(llm, template_name, tools)
        self.memory = memory_store
    
    def render_human_message(self, task: str, action_history: list) -> HumanMessage:
        """
        Formats the raw action history into a request for an SOP.
        """
        content = f"""
        --- COMPLETED TASK ---
        "{task}"
        
        --- RAW ACTION HISTORY ---
        {action_history}
        
        --- INSTRUCTIONS ---
        Convert this history into a GENERIC Standard Operating Procedure (SOP).
        1. Generalize coordinates (e.g., don't say "Move to (1,2)", say "Move to Fridge").
        2. Keep it concise (3-6 steps).
        3. Output strict JSON matching the SkillDTO structure.
        """
        return HumanMessage(content=content)
    
    async def retrieve_skill(self, task: str):
        """
        Finds a relevant guide for the current task to inject into the Context.
        """
        try:
            query = f"How to {task}"
            skills: list[SkillDTO] = await self.memory.fetch_similar_skills(query=query, limit=1)
            
            #TODO: 
            if not skills:
                return ""
            
            #TODO: strategy for use which relavent skill
            best_skill = skills[0]
            
            return f"""
            --- KNOWN RECIPE / SKILL ---
            Task: {best_skill.task_name}
            Description: {best_skill.description}
            Guide:
            {best_skill.steps_text}
            """ 
        except Exception as e:
            logger.error(f"Failed to retrieve skill for '{task}': {e}")
            return ""
        
    
    async def learn_new_skill(
        self, 
        task: str, 
        action_history: list, 
        success: bool,
        max_retries=3):
        """
        Called after Critic says 'Success'.
        Summarizes the raw JSON actions into a generic textual guide.
        """
        if not success:
            return
        
        if max_retries == 0:
            logger.error(f"Failed to learn skill '{task}' after max retries.")
            return
        
        sys_msg = self.render_system_message().content
        human_msg = self.render_human_message(task, action_history).content
        
        try:
            sop_resp = await self.llm.generate_response(
                system_prompt=sys_msg,
                user_message=human_msg
            )
            
            
            print(f"\n\n[LLM response]:{sop_resp}\n")
            logger.info(f"\n\n[LLM response]:{sop_resp}\n")
            
            data = self._parse_json_helper(sop_resp)

            if not data:
                raise ValueError("No JSON found")
            if isinstance(data, list):
                data = data[0]
                
            new_skill = SkillDTO(**data)
            
            await self.memory.save_skill(new_skill)
            logger.info(f"🧠 Learned new skill: {task}")
        
        except Exception as e:
            logging.warning(f"Error learning skill: {e}. Retrying ({max_retries} left)...")
            return await self.learn_new_skill(
                task,
                action_history,
                success,
                max_retries - 1
            )
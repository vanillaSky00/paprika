import logging
from langchain_core.messages import HumanMessage
from app.api.schemas import Perception, CriticOutput
from app.llm.base import BaseLLMClient
from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class CriticAgent(BaseAgent):
    def __init__(
        self, 
        llm: BaseLLMClient, 
        template_name="critic", 
        tools=None,
        mode="auto"):
        super().__init__(llm, template_name, tools)
        self.mode = mode
        
    def render_human_message(
        self,
        perception: Perception,
        current_task: str
        ) -> HumanMessage:
        """
        Compare the TASK (Goal) vs. the OBSERVATION (Result).
        """
        visible_objects = ", ".join(
            [f"{o.id}({o.state})" for o in perception.nearby_objects]
        ) or "None"
        
        content = f"""
        --- GOAL ---
        {current_task}

        --- CURRENT STATE ---
        Location: {perception.location_id}
        Holding: {perception.held_item or "Nothing"}
        Visible Objects: {visible_objects}
        
        --- SYSTEM FEEDBACK ---
        Last Action Status: {perception.last_action_status or "None"}
        Last Error: {perception.last_action_error or "None"}
        """
        return HumanMessage(content=content)
    
    # Check entry point, act as router 
    async def check_task_success(
        self,
        perception: Perception,
        current_task: str,
        max_retries=5
    ):
  
        sys_msg_content = self.render_system_message().content
        human_msg_content = self.render_human_message(perception, current_task).content
        
        if self.mode == "manual":
            return self.human_check_task_success()
        
        elif self.mode == "auto":
            return await self.ai_check_task_success(
                sys_msg_content, 
                human_msg_content,
                max_retries
            )
            
        else:
            raise ValueError(f"Invalid mode: {self.mode}")
        
    async def ai_check_task_success(
            self, 
            sys_msg, 
            human_msg,
            max_retries
        ) -> CriticOutput:
        if max_retries == 0:
            logger.critical("Failed to parse Critic Agent response. Max retries reached.")
            return CriticOutput(
                success=False,
                reasoning="Max retries",
                feedback="System Error"
            )

        try:
            response_text = await self.llm.generate_response(
                system_prompt=sys_msg,
                user_message=human_msg
            )
            
            logger.info(f"\n\n[LLM response]:{response_text}\n")
            
            data = self._parse_json_helper(response_text)
            
            if not data:
                raise ValueError("No JSON found")
            if isinstance(data, list):
                data = data[0]
            
            return CriticOutput(**data)
        
        except Exception as e:
            logger.warning(f"Error parsing critic response: {e}. Retrying ({max_retries} left)...")
            return await self.ai_check_task_success(
                sys_msg,
                human_msg,
                max_retries=max_retries - 1
            )
    
    # for dev
    def human_check_task_success(self):
        logger.info("\n--- HUMAN CRITIC MODE ---")
        
        while True:
            success_input = input("Success? (y/n): ").strip().lower()
            if success_input in ['y', 'n']:
                break
        
        is_success = (success_input == 'y')
        reasoning = input("Reasoning: ").strip()
        feedback = input("Feedback: ").strip()
        
        return CriticOutput(
            is_success,
            reasoning,
            feedback
        )
        
    
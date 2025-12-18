import re
import json
import logging
from abc import ABC
from langchain_core.messages import SystemMessage
from langchain_core.tools import StructuredTool
from app.llm.base import BaseLLMClient
from app.prompts import loader as ld

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    def __init__(
        self, 
        llm: BaseLLMClient, 
        template_name: str, 
        tools: list[StructuredTool] | None = None
    ):
        self.llm = llm
        self.tools = tools or []
        self.system_prompts = ld.build_system_prompt(template_name, self.tools)
        
    def render_system_message(self) -> SystemMessage:
        return SystemMessage(content=self.system_prompts)
    
    def _parse_json_helper(self, content: str) -> list | dict | None:
        """
        Shared Logic: Regex -> Python Object (Dict/List)
        """
        try:
            # 1. Try list
            match_list = re.search(r"\[.*\]", content, re.DOTALL)
            if match_list:
                return json.loads(match_list.group(0))

            # 2. Try object
            match_obj = re.search(r"\{.*\}", content, re.DOTALL)
            if match_obj:
                return json.loads(match_obj.group(0))

            logger.warning(f"No JSON found. First 100 chars: {content[:100]}...")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"JSON Decode Failed: {e}", extra={"content": content})
            return None
from abc import ABC, abstractmethod
import logging
from langchain_core.tools import StructuredTool
from .context import ToolContext

logger = logging.getLogger(__name__)

class BaseToolBuilder(ABC):
    @abstractmethod
    def build(self, context: ToolContext) -> StructuredTool | None:
        pass
    
class ToolRegistry:
    def __init__(self):
        """
        Store the class itself, not an instantiated object. 
        
        Consider:
        Dict[str, BaseToolBuilder]
            {
            "WeatherToolBuilder": WeatherToolBuilder()   # instance
            }
        
        But we want
            {
            "WeatherToolBuilder": WeatherToolBuilder     # class
            }
        """
        self._builders: dict[str, type[BaseToolBuilder]] = {}
        self._shortcuts: dict[str, str] = {} # handle naming collsion
        
    def register(self, cls: type[BaseToolBuilder]) -> type[BaseToolBuilder]:
        """
        DECORATOR: Signs a class up for the talent show.
        Usage: 
            @registry.register
            class WeatherToolBuilder(BaseToolBuilder):
                pass
        """
        #self._builders[cls.__name__] = cls # would crash if same class name in different modules
        full_name = f"{cls.__module__}.{cls.__name__}"
        short_name = cls.__name__
        
        if full_name in self._builders:
            logger.warning(f"Overwriting existing tool registration: {full_name}")
        
        self._builders[full_name] = cls
        
        if short_name not in self._shortcuts:
            self._shortcuts[short_name] = full_name
        else:
            logger.warning(f"Name collision detected for '{short_name}'. Removing shortcut. Use full path.")
            del self._shortcuts[short_name]
        
        return cls
    
    def build_all(self, context: ToolContext) -> list[StructuredTool]:
        """
        The 'Late Binding' Event.
        Happens only once, when the server starts.
        """
        active_tools = []
        logger.info("Initializing %d tools...", len(self._builders))
        
        for name, BuilderClass in self._builders.items():
            self._safe_build(name, BuilderClass, context, active_tools)
            
        return active_tools
    
    def build_selected(self, names: list[str], context: ToolContext) -> list[StructuredTool]:
        """
        Builds only a specific subset of tools.
        Useful for assigning specific skills to specific agents.
        """
        tools = []
        for name in names:
            if name in self._builders:
                self._safe_build(name, self._builders[name], context, tools)
                continue
            
            resolved_name = self._shortcuts.get(name)
            if resolved_name and resolved_name in self._builders:
                self._safe_build(resolved_name, self._builders[resolved_name], context, tools)
            else:
                logger.error(f"Requested tool '{name}' not found.")
                
        return tools
    
    def _safe_build(self, name: str, BuilderClass: type[BaseToolBuilder], context: ToolContext, target_list: list[StructuredTool]):
        try:
            builder = BuilderClass()
            tool = builder.build(context)
            
            if tool:
                target_list.append(tool)
                logger.info(f"Tool '{name}' loaded successfully.")
            else:
                logger.warning(f"Tool '{name}' skipped due to missing configuration.")

        except Exception:
            logger.exception(f"Tool '{name}' failed to build.")
  
    
tool_registry = ToolRegistry()
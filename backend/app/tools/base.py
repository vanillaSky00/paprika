import logging
from abc import ABC, abstractmethod
from langchain_core.tools import StructuredTool

from app.tools.context import ToolContext

logger = logging.getLogger(__name__)


class BaseToolBuilder(ABC):
    @abstractmethod
    def build(self, context: ToolContext) -> StructuredTool | None:
        pass


class ToolRegistry:
    def __init__(self):
        self._builders: dict[str, type[BaseToolBuilder]] = {}
        self._shortcuts: dict[str, str] = {}
        self._seen_shortcuts: set[str] = set()

    def register(self, cls: type[BaseToolBuilder]) -> type[BaseToolBuilder]:
        """
        DECORATOR: Signs a class up for the talent show.
        """
        full_name = f"{cls.__module__}.{cls.__name__}"
        short_name = cls.__name__

        # 1. Always store the safe Full Name
        if full_name in self._builders:
            logger.warning(f"Overwriting existing tool registration: {full_name}")
        self._builders[full_name] = cls

        # 2. Manage the Shortcut (Collision Logic)
        if short_name in self._shortcuts:
            # Collision #1: Second time we see this name. Remove ambiguity.
            logger.warning(
                f"Name collision detected for '{short_name}'. Removing shortcut. Use full path."
            )
            del self._shortcuts[short_name]
        elif short_name in self._seen_shortcuts:
            # Collision #2+: We already banned this. Warn and ignore.
            logger.warning(
                f"Name collision: '{short_name}' (3rd+ copy). Shortcut remains banned."
            )
        else:
            # Unique so far: Create shortcut.
            self._shortcuts[short_name] = full_name
            self._seen_shortcuts.add(short_name)

        return cls

    def build_all(self, context: ToolContext) -> list[StructuredTool]:
        """
        The 'Late Binding' Event. Happens only once at startup.
        """
        active_tools = []
        logger.info("Initializing %d tools...", len(self._builders))

        for name, BuilderClass in self._builders.items():
            self._safe_build(name, BuilderClass, context, active_tools)

        return active_tools

    def build_selected(
        self, names: list[str], context: ToolContext
    ) -> list[StructuredTool]:
        """
        Builds only a specific subset of tools.
        """
        tools = []
        for name in names:
            # Try full name first
            if name in self._builders:
                self._safe_build(name, self._builders[name], context, tools)
                continue

            # Then try shortcut
            resolved_name = self._shortcuts.get(name)
            if resolved_name and resolved_name in self._builders:
                self._safe_build(
                    resolved_name, self._builders[resolved_name], context, tools
                )
            else:
                logger.error(f"Requested tool '{name}' not found.")

        return tools

    def _safe_build(
        self,
        name: str,
        BuilderClass: type[BaseToolBuilder],
        context: ToolContext,
        target_list: list[StructuredTool],
    ):
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

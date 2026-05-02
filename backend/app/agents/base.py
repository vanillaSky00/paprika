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
        tools: list[StructuredTool] | None = None,
    ):
        self.llm = llm
        self.tools = tools or []
        self.system_prompts = ld.build_system_prompt(template_name, self.tools)

    def render_system_message(self) -> SystemMessage:
        return SystemMessage(content=self.system_prompts)

    def _parse_json_helper(self, content: str) -> list | dict | None:
        """Extract a JSON value (list or dict) from model output.

        Why not just `json.loads(content)`? LLMs sometimes wrap the JSON
        in prose, markdown code fences, or a leading "Here's the JSON:"
        preamble. We try progressively looser strategies and crucially
        try BOTH shapes independently — a previous version returned None
        the first time a regex bracket match failed to parse, so
        responses with `[C]` / `[B]` references inside a reasoning
        string were incorrectly dropped.
        """
        stripped = content.strip()

        # 1. Pure JSON (most common when the model follows instructions).
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

        # 2. Strip markdown code fences (```json ... ``` or ``` ... ```).
        fenced = re.sub(
            r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.MULTILINE,
        ).strip()
        if fenced != stripped:
            try:
                return json.loads(fenced)
            except json.JSONDecodeError:
                pass

        # 3. Balanced-bracket extraction. Walk the string looking for a
        # top-level `{...}` or `[...]` that parses cleanly. Objects are
        # tried before lists because when a critic/curriculum reply like
        #     {"task": "X", "reasoning": "[C] shows ..."}
        # runs the old regex first, the `[C]` inside reasoning wins and
        # the whole response is lost.
        for open_ch, close_ch in (("{", "}"), ("[", "]")):
            parsed = self._extract_balanced(content, open_ch, close_ch)
            if parsed is not None:
                return parsed

        logger.warning("No JSON found. First 200 chars: %s", content[:200])
        return None

    @staticmethod
    def _extract_balanced(
        content: str, open_ch: str, close_ch: str,
    ) -> list | dict | None:
        """Find every top-level `open_ch...close_ch` block and return
        the first one that parses as JSON."""
        i = 0
        while True:
            start = content.find(open_ch, i)
            if start == -1:
                return None
            depth = 0
            end = -1
            in_string = False
            escape = False
            for j in range(start, len(content)):
                ch = content[j]
                if escape:
                    escape = False
                    continue
                if ch == "\\":
                    escape = True
                    continue
                if ch == '"':
                    in_string = not in_string
                    continue
                if in_string:
                    continue
                if ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        end = j
                        break
            if end == -1:
                return None
            try:
                return json.loads(content[start:end + 1])
            except json.JSONDecodeError:
                i = start + 1  # try next occurrence

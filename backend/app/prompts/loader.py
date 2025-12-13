import json
from pathlib import Path

from langchain_core.tools import StructuredTool

BASE_DIR = Path(__file__).parent / "templates"


def build_system_prompt(template_name: str, tools: list[StructuredTool] | None) -> str:
    tools_doc = _load_tool_definition(tools=tools) or ""
    raw_text = _load_system_template(template_name=template_name)
    return raw_text.format(tools_doc=tools_doc)


def _load_system_template(template_name: str) -> str:
    file_path = BASE_DIR / f"{template_name}.md"
    try:
        return file_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"ERROR: {file_path} not found")


def _load_tool_definition(tools: list[StructuredTool]) -> str:
    if not tools:
        return ""
    
    documentation_lines = []

    for tool in tools:
        try:
            if tool.args_schema:
                args_schema = json.dumps(
                    tool.args_schema.model_json_schema()["properties"]
                )
            else:
                args_schema = "None"
        except Exception:
            args_schema = "Unknown"

        doc_entry = f"""
        - Function: {tool.name}
        - Description: {tool.description}
        - Argument: {args_schema}
        """
        documentation_lines.append(doc_entry.strip())

    return "\n\n".join(documentation_lines)

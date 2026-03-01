"""MCP script generator — wraps CreateLibEnsembleScripts as a LangChain tool."""

import re

from langchain_core.tools import StructuredTool

from .base import ToolProvider


class GeneratorTools(ToolProvider):
    """Wraps the MCP CreateLibEnsembleScripts tool as a LangChain tool."""

    def __init__(self, config, archive):
        super().__init__(config, archive)
        self._session = None
        self._mcp_tool_schema = None

    def set_mcp_session(self, session):
        self._session = session

    def set_mcp_tool_schema(self, schema):
        """Store the MCP tool schema for building the LangChain tool."""
        self._mcp_tool_schema = schema

    def get_tools(self):
        if self._mcp_tool_schema is None:
            return []

        session = self._session
        work_dir = self.archive.work_dir
        archive = self.archive
        tool_schema = self._mcp_tool_schema

        async def generate_scripts_mcp(**kwargs):
            """Call MCP tool to generate scripts, auto-save to work dir."""
            # Block custom_set_objective — AI always gets it wrong
            kwargs.pop("custom_set_objective", None)
            kwargs.pop("set_objective_code", None)

            result = await session.call_tool("CreateLibEnsembleScripts", kwargs)
            scripts_text = result.content[0].text if result.content else ""

            if scripts_text and "===" in scripts_text:
                work_dir.mkdir(exist_ok=True)
                pattern = r"=== (.+?) ===\n(.*?)(?=\n===|$)"
                for filename, content in re.findall(pattern, scripts_text, re.DOTALL):
                    (work_dir / filename.strip()).write_text(content.strip() + "\n")
                    print(f"- Saved: {work_dir / filename.strip()}", flush=True)
                archive.start("generated")
                archive.archive_scripts()

            return scripts_text

        return [
            StructuredTool(
                name=tool_schema.name,
                description=tool_schema.description,
                args_schema=tool_schema.inputSchema,
                coroutine=generate_scripts_mcp,
            ),
        ]

    def get_prompt_fragment(self):
        if self._mcp_tool_schema is not None:
            return (
                "You have a CreateLibEnsembleScripts tool. "
                "Use it ONCE to generate initial scripts. "
                "For modifications, use read_file + write_file instead."
            )
        return ""

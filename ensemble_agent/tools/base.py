"""Base class for tool providers."""

from abc import ABC, abstractmethod


class ToolProvider(ABC):
    """Provides a group of related LangChain tools to the agent."""

    def __init__(self, config, archive):
        self.config = config
        self.archive = archive

    @abstractmethod
    def get_tools(self):
        """Return list of LangChain StructuredTool instances."""
        ...

    def get_prompt_fragment(self):
        """Return text to inject into the system prompt, or empty string."""
        return ""

    def set_mcp_session(self, session):
        """Inject an MCP session (called by orchestrator for MCP-dependent tools)."""
        pass

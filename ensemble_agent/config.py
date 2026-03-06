"""Agent configuration, CLI parsing, and constants."""

import os
import sys
import argparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Execution
MAX_RUNS = 3
SCRIPT_TIMEOUT = 300  # seconds
MAX_AGENT_ITERATIONS = 15

# Default models
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_ARGO_MODEL = "claude-opus-4-6"

# Storage
ARCHIVE_RUNS_DIR = "archive_runs"
DEFAULT_OUTPUT_DIR = "generated_scripts"

# Artifacts to archive after each run
ARCHIVE_ITEMS = [
    "ensemble",
    "ensemble.log",
    "libE_stats.txt",
    "*.npy",
    "*.pickle",
]

# UI
INPUT_MARKER = "[INPUT_REQUESTED]"


def _has_anthropic_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _is_argo() -> bool:
    return bool(os.environ.get("ANTHROPIC_BASE_URL") and _has_anthropic_key())


def _default_model() -> str:
    """Pick default model based on available API keys."""
    if os.environ.get("LLM_MODEL"):
        return os.environ["LLM_MODEL"]
    if _is_argo():
        return DEFAULT_ARGO_MODEL
    if os.environ.get("OPENAI_API_KEY") or not _has_anthropic_key():
        return DEFAULT_OPENAI_MODEL
    return DEFAULT_ANTHROPIC_MODEL


@dataclass
class AgentConfig:
    """All agent configuration in one place."""

    # Mode
    interactive: bool = False
    generate_only: bool = False

    # Input
    scripts_dir: Optional[str] = None
    prompt: Optional[str] = None
    prompt_file: Optional[str] = None

    # LLM
    model: str = field(default_factory=_default_model)
    temperature: float = 0
    base_url: Optional[str] = field(
        default_factory=lambda: os.environ.get("OPENAI_BASE_URL")
    )

    # MCP servers
    mcp_server: Optional[str] = None
    mcp_tools: bool = False

    # Output
    output_dir: str = DEFAULT_OUTPUT_DIR
    show_prompts: bool = False
    debug: bool = False

    # Execution limits
    max_runs: int = MAX_RUNS
    max_iterations: int = MAX_AGENT_ITERATIONS
    script_timeout: int = SCRIPT_TIMEOUT

    def get_user_prompt(self) -> Optional[str]:
        """Resolve the user prompt from --prompt, --prompt-file, or default."""
        if self.scripts_dir:
            return None
        if self.prompt_file:
            return Path(self.prompt_file).read_text()
        if self.prompt:
            return self.prompt
        return None


def parse_args(argv=None) -> AgentConfig:
    """Parse CLI arguments into AgentConfig."""
    # Argo: use ANTHROPIC_AUTH_TOKEN as API key
    if os.environ.get("ANTHROPIC_AUTH_TOKEN") and not os.environ.get("ANTHROPIC_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_AUTH_TOKEN"]

    parser = argparse.ArgumentParser(
        description="Ensemble agent for generating, running, and fixing simulation scripts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ensemble_agent.py --interactive
  python ensemble_agent.py --scripts tests/scripts_with_errors/
  python ensemble_agent.py --prompt "Create APOSMM scripts..."
        """,
    )
    parser.add_argument("--interactive", action="store_true", help="Enable interactive chat mode")
    parser.add_argument("--scripts", dest="scripts_dir", help="Use existing scripts from directory")
    parser.add_argument("--prompt", help="Prompt for script generation")
    parser.add_argument("--prompt-file", help="Read prompt from file")
    parser.add_argument("--model", default=None, help="LLM model name")
    parser.add_argument("--mcp-server", help="Path to generator mcp_server.mjs")
    parser.add_argument("--mcp-tools", action="store_true", help="Run local tools as FastMCP server (subprocess)")
    parser.add_argument("--generate-only", action="store_true", help="Only generate scripts, don't run")
    parser.add_argument("--show-prompts", action="store_true", help="Print prompts sent to AI")
    parser.add_argument("--debug", action="store_true", help="Dump full message log to debug_log.txt")
    parser.add_argument("--max-iterations", type=int, default=MAX_AGENT_ITERATIONS, help="Max agent iterations")
    args = parser.parse_args(argv)

    config = AgentConfig(
        interactive=args.interactive,
        generate_only=args.generate_only,
        scripts_dir=args.scripts_dir,
        prompt=args.prompt,
        prompt_file=args.prompt_file,
        mcp_server=args.mcp_server,
        mcp_tools=args.mcp_tools,
        show_prompts=args.show_prompts,
        debug=args.debug or bool(os.environ.get("AGENT_DEBUG")),
        max_iterations=args.max_iterations,
    )
    if args.model:
        config.model = args.model

    return config

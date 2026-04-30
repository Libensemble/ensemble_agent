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
# Default models
DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-7"

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
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _is_argo() -> bool:
    return bool(os.environ.get("ANTHROPIC_BASE_URL") and _has_anthropic_key())


def _default_model() -> str:
    """Pick default model based on available API keys."""
    if os.environ.get("LLM_MODEL"):
        return os.environ["LLM_MODEL"]
    if _has_anthropic_key():
        return DEFAULT_ANTHROPIC_MODEL
    if os.environ.get("OPENAI_API_KEY"):
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
    run_script: Optional[str] = None
    prompt: Optional[str] = None
    prompt_file: Optional[str] = None

    # LLM
    model: str = field(default_factory=_default_model)
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
    script_timeout: int = SCRIPT_TIMEOUT

    # Permissions
    allow_install: bool = False

    # Remote execution: "system:endpoint" (e.g., "polaris:polaris-libe")
    remote: Optional[str] = None

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
    parser.add_argument("script", nargs="?", default=None, help="Path to a script file to run/fix")
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
    parser.add_argument("--allow-install", action="store_true", help="Allow agent to pip install packages in autonomous mode")
    parser.add_argument("--remote", help="Run on a run-target as SYSTEM:ENDPOINT, e.g., polaris:polaris-libe")
    parser.add_argument("--run-targets", dest="run_targets", help="Path to run-targets dir (default: ./run_targets)")
    args = parser.parse_args(argv)

    # Positional script arg: treat its directory as scripts_dir
    scripts_dir = args.scripts_dir
    run_script = None
    if args.script:
        script_path = Path(args.script)
        if not script_path.exists():
            parser.error(f"Script not found: {args.script}")
        scripts_dir = str(script_path.parent)
        run_script = script_path.name

    config = AgentConfig(
        interactive=args.interactive,
        generate_only=args.generate_only,
        scripts_dir=scripts_dir,
        run_script=run_script,
        prompt=args.prompt,
        prompt_file=args.prompt_file,
        mcp_server=args.mcp_server,
        mcp_tools=args.mcp_tools,
        show_prompts=args.show_prompts,
        debug=args.debug or bool(os.environ.get("AGENT_DEBUG")),
    )
    if args.model:
        config.model = args.model
    if args.allow_install:
        config.allow_install = True
    if args.remote:
        config.remote = args.remote
    if args.run_targets:
        from .remote.run_targets import set_dir
        set_dir(args.run_targets)

    return config

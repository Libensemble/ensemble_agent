"""Agent orchestrator — builds the agent, runs autonomous or interactive mode."""

import re
import shutil
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain_mcp_adapters.tools import load_mcp_tools

from .archive import ArchiveManager
from .config import AgentConfig, INPUT_MARKER
from .debug import DebugLogger
from .llm import create_llm
from .mcp_client import connect_mcp, connect_tool_server, find_mcp_server
from .prompts import (
    AUTONOMOUS_GOAL,
    INTERACTIVE_GOAL,
    INTERACTIVE_REVIEW_GOAL,
    build_system_prompt,
)
from . import tool_server

_TESTS_DIR = str(Path(__file__).parent.parent / "tests")

DEFAULT_PROMPT = f"""Create six_hump_camel APOSMM scripts:
- Executable: {_TESTS_DIR}/six_hump_camel/six_hump_camel.x
- Input: {_TESTS_DIR}/six_hump_camel/input.txt
- Template vars: X0, X1
- 4 workers, 100 sims.
- The output file for each simulation is output.txt
- The bounds should be 0,1 and -1,2 for X0 and X1 respectively"""


async def run_agent(config: AgentConfig):
    """Main entry point: build tools, connect MCP, run the agent loop."""

    # Archive existing output dir before starting fresh
    ArchiveManager.archive_existing_output_dir(config.output_dir)

    # Set up archive manager
    archive = ArchiveManager(config.output_dir)

    # Debug logger
    debug = None
    if config.debug:
        log_path = Path(config.output_dir) / "debug_log.txt"
        debug = DebugLogger(log_path, model=config.model)

    has_generator = not config.scripts_dir

    async with AsyncExitStack() as stack:
        # Load local tools
        if config.mcp_tools:
            # MCP mode: run tools as FastMCP subprocess
            tool_session = await stack.enter_async_context(connect_tool_server(config))
            tools = await load_mcp_tools(tool_session)
        else:
            # In-process mode (default)
            tool_server.init(config, archive)
            tools = tool_server.get_langchain_tools()

        # Connect to generator MCP (if available)
        if has_generator:
            try:
                mcp_server = find_mcp_server(config.mcp_server)
                print(f"Generator MCP: {mcp_server}")
                gen_session = await stack.enter_async_context(connect_mcp(mcp_server))
                print("Connected to generator MCP server")
                gen_tools = await load_mcp_tools(gen_session)
                gen_tool = _wrap_generator_tool(gen_tools[0], archive.work_dir)
                tools.append(gen_tool)
            except (FileNotFoundError, Exception) as e:
                print(f"Generator MCP not available: {e}")
                print("Continuing without script generator")
                has_generator = False

        # Create LLM and agent
        llm, service = create_llm(config.model, config.temperature, config.base_url)
        agent = create_agent(llm, tools)
        print(f"Agent initialized (model: {config.model}, service: {service})\n")

        # Build system prompt
        system_prompt = build_system_prompt(has_generator)
        messages = [("system", system_prompt)]

        if debug:
            debug.log_system_prompt(system_prompt)
            debug.log_tool_schemas(tools)

        if config.show_prompts:
            print(f"System prompt:\n{system_prompt}\n")

        # Determine initial message
        initial_msg = _build_initial_message(config, archive)

        if not config.interactive:
            await _run_autonomous(agent, messages, initial_msg, config, debug)
        else:
            await _run_interactive(agent, messages, initial_msg, config, has_generator, debug)


def _wrap_generator_tool(raw_tool, work_dir):
    """Wrap the MCP generator tool to auto-save generated files."""
    original_coroutine = raw_tool.coroutine

    async def wrapped(**kwargs):
        kwargs.pop("custom_set_objective", None)
        kwargs.pop("set_objective_code", None)

        scripts_text = await original_coroutine(**kwargs)

        if scripts_text and "===" in scripts_text:
            work_dir.mkdir(exist_ok=True)
            pattern = r"=== (.+?) ===\n(.*?)(?=\n===|$)"
            for filename, content in re.findall(pattern, scripts_text, re.DOTALL):
                (work_dir / filename.strip()).write_text(content.strip() + "\n")
                print(f"- Saved: {work_dir / filename.strip()}", flush=True)

        return scripts_text

    return StructuredTool(
        name=raw_tool.name,
        description=raw_tool.description,
        args_schema=raw_tool.args_schema,
        coroutine=wrapped,
    )


def _build_initial_message(config, archive):
    """Build the first user message based on config."""
    if config.scripts_dir:
        scripts_dir = Path(config.scripts_dir)
        for f in sorted(scripts_dir.glob("*.py")):
            shutil.copy(f, archive.work_dir)
            print(f"Copied: {f.name}")
        archive.start("copied_scripts")
        archive.archive_scripts()

        run_scripts = list(archive.work_dir.glob("run_*.py"))
        run_name = run_scripts[0].name if run_scripts else "run_libe.py"
        return INTERACTIVE_REVIEW_GOAL.format(run_script_name=run_name)

    user_prompt = config.get_user_prompt()
    if user_prompt:
        return user_prompt

    if config.interactive:
        print("Describe the scripts you want to generate (or press Enter for default demo):", flush=True)
        if not sys.stdout.isatty():
            print(INPUT_MARKER, flush=True)
        user_input = input(">>> ").strip()
        if user_input:
            return user_input

    print(f"Using demo prompt:\n{DEFAULT_PROMPT}\n")
    return DEFAULT_PROMPT


async def _run_autonomous(agent, messages, initial_msg, config, debug):
    """Single invocation — agent generates/loads, runs, fixes, reports."""
    goal = AUTONOMOUS_GOAL.format(initial_msg=initial_msg)
    messages.append(("user", goal))

    if config.show_prompts:
        print(f"Goal: {goal}\n")
    print("Starting agent...\n")

    result = await agent.ainvoke({"messages": messages})
    if debug:
        debug.dump_messages(result["messages"], "Autonomous run complete")
    print(f"\n{'=' * 60}")
    print("Agent completed")
    print(f"{'=' * 60}")
    content = result["messages"][-1].content
    if isinstance(content, list):
        content = "".join(block.get("text", "") for block in content)
    print(content)


async def _run_interactive(agent, messages, initial_msg, config, has_generator, debug):
    """Chat loop — agent responds, waits for user input, repeats."""
    if config.scripts_dir:
        # Auto-review, fix, run scripts first, then enter chat
        goal = AUTONOMOUS_GOAL.format(initial_msg=initial_msg)
    elif has_generator:
        goal = INTERACTIVE_GOAL.format(initial_msg=initial_msg)
    else:
        goal = initial_msg
    messages.append(("user", goal))
    print("Starting agent...\n")
    turn = 0

    while True:
        try:
            result = await agent.ainvoke({"messages": messages})
            messages = result["messages"]
            turn += 1
            if debug:
                debug.dump_messages(messages, f"Interactive turn {turn}")
            response = messages[-1].content
            if isinstance(response, list):
                response = "".join(block.get("text", "") for block in response)
            if response:
                print(f"\n{response}", flush=True)
        except Exception as e:
            print(f"\nAgent error: {e}", flush=True)

        # Wait for user input
        print("\nEnter a follow-up request (or Enter to quit):", flush=True)
        if not sys.stdout.isatty():
            print(INPUT_MARKER, flush=True)
        user_input = input(">>> ").strip()

        if not user_input or user_input.lower() in ("q", "quit", "exit", "done"):
            print("\nSession ended")
            break

        messages.append(HumanMessage(content=user_input))

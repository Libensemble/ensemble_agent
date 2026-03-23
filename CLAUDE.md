# CLAUDE.md

## Project Overview

An agentic system for generating, running, and iteratively fixing simulation scripts (currently libEnsemble, designed to support other ensemble tools). Uses LangChain ReAct agents with tools exposed via MCP and local Python functions.

## Package Structure

```
ensemble_agent.py              # Wrapper script entry point
ensemble_agent/                # Main package (also: python -m ensemble_agent)
    config.py                  # AgentConfig dataclass, parse_args(), constants
    llm.py                     # create_llm() → (llm, service_label) tuple
    agent.py                   # Orchestrator: build agent, run autonomous or interactive
    prompts.py                 # System prompt templates
    archive.py                 # ArchiveManager: versioned script+output tracking
    scripts.py                 # Script parsing (=== format), saving, detection
    tool_server.py             # Tools: also runs as standalone MCP server (FastMCP)
    mcp_client.py              # MCP server discovery + connect_mcp()
    create_examples_index.py   # Generates indexes of example source files
    debug.py                   # DebugLogger for message history dumps
    plotting/                  # Visualization of optimization results
    reference_docs/            # Markdown guides loaded via load_guide tool
tests/                         # Test scripts with intentional errors
web_ui/                        # Gradio web interface
misc/                          # Standalone demonstrators (e.g. fixup_agent.py)
.claude/skills/                # Claude Code skills for workflow automation
```

## Running

```bash
python ensemble_agent.py --scripts tests/scripts_with_errors/   # Fix existing scripts
python ensemble_agent.py --interactive                          # Generate via MCP + chat
python ensemble_agent.py --prompt "Create APOSMM scripts..."    # Generate from prompt
python ensemble_agent.py --debug                                # Write debug_log.txt
```

## MCP Server Setup (Script Generation)

The script generator runs as an MCP server in a separate repo. It is required
for `--interactive` and `--prompt` modes but not for `--scripts` (fix-only) mode.

```bash
# Clone the generator repo
git clone https://github.com/Libensemble/script-creator.git

# Point ensemble_agent to the MCP server
export GENERATOR_MCP_SERVER=/path/to/script-creator/mcp_server.mjs
# or pass it directly:
python ensemble_agent.py --mcp-server /path/to/script-creator/mcp_server.mjs
```

The MCP server requires Node.js (`node` on PATH) since it is a `.mjs` file.

## Environment Variables

```
OPENAI_API_KEY / ANTHROPIC_API_KEY    # LLM auth
ANTHROPIC_BASE_URL / OPENAI_BASE_URL  # Custom endpoints
LLM_MODEL                            # Override default model
GENERATOR_MCP_SERVER                  # Path to mcp_server.mjs (see above)
AGENT_DEBUG                           # Enable debug logging
```

## Key Implementation Details

- `streaming=True` on ChatAnthropic required for Argo gateway.
- Anthropic streaming returns list content — `isinstance(content, list)` check extracts text.
- Generator tool auto-excluded when `--scripts` is passed.
- Run limits enforced in tool_server.py (`_max_runs` counter). Prompts guide stop-after-success behavior.
- Existing `generated_scripts/` moved to `archive_runs/` before each fresh run.

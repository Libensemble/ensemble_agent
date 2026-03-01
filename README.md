# Ensemble Agent

An agentic system for generating, running, and iteratively fixing simulation scripts. Currently supports [libEnsemble](https://github.com/Libensemble/libensemble), designed to extend to other ensemble tools.

Uses LangChain ReAct agents with tools exposed via MCP and local Python functions.

## Installation

Dependencies (no package installer yet):

    pip install langchain langchain-openai langchain-anthropic mcp

For the web UI:

    pip install gradio fastapi uvicorn[standard] websockets

## MCP Server Setup (Script Generation)

The script generator runs as an MCP server from a separate repository. It is required for `--interactive` and `--prompt` modes but **not** for `--scripts` (fix-only) mode.

```bash
git clone https://github.com/Libensemble/script-creator.git
export GENERATOR_MCP_SERVER=/path/to/script-creator/mcp_server.mjs
```

Or pass it directly:

```bash
python ensemble_agent.py --mcp-server /path/to/script-creator/mcp_server.mjs
```

The MCP server requires Node.js (`node` on PATH).

## Usage

```bash
# Fix existing scripts
python ensemble_agent.py --scripts tests/scripts_with_errors/

# Generate scripts interactively via MCP
python ensemble_agent.py --interactive

# Generate from a prompt
python ensemble_agent.py --prompt "Create APOSMM scripts..."

# Enable debug logging
python ensemble_agent.py --debug
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `ANTHROPIC_AUTH_TOKEN` | Argo gateway token (auto-mapped to `ANTHROPIC_API_KEY`) |
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint |
| `ANTHROPIC_BASE_URL` | Custom Anthropic endpoint |
| `LLM_MODEL` | Override default model |
| `GENERATOR_MCP_SERVER` | Path to `mcp_server.mjs` |
| `AGENT_DEBUG` | Enable debug logging |

## Web UI

A Gradio web interface is available in `web_ui/`. See [web_ui/README.md](web_ui/README.md) for details.

```bash
cd web_ui
python gradio_ui.py
```
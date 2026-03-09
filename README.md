# Ensemble Agent

An agentic system for generating, running, and iteratively fixing simulation scripts. Currently supports [libEnsemble](https://github.com/Libensemble/libensemble), designed to extend to other ensemble tools.

Uses LangChain ReAct agents with tools exposed via MCP and local Python functions.

## Installation

Dependencies (no package installer yet):

    pip install langchain langchain-openai langchain-anthropic mcp

For the web UI:

    pip install gradio fastapi uvicorn[standard] websockets

## MCP Server Setup (Script Generation)

The script generator runs as an MCP server from a separate repository.
It is **not** requied when user scripts are specified via `--scripts` option.

```bash
sudo apt install nodejs
git clone https://github.com/Libensemble/script-creator.git
cd script-creator
npm install

export GENERATOR_MCP_SERVER="$(pwd)/mcp_server.mjs"
```

## Options for LLM model keys

For all workflows, you will need a key to access an LLM.

For example, you can set an OpenAPI key.
Requires an [OpenAI account](https://platform.openai.com).
Make sure to check MODEL at top of agentic script and usage rates.

Set user OpenAI API Key:

```bash
export OPENAI_API_KEY="sk-your-key-here"
```

Or if you use Anthropic, you can set.

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
```

Optionally, you can set the `LLM_MODEL` env variable to a model name.
However, if using the Web UI, there is a drop down select of available models.


<details>
<summary>Using Argo gateway (optional)</summary>

If you have access to Argo, you can use it as an Anthropic gateway:

```bash
export ANTHROPIC_BASE_URL="https://apps-dev.inside.anl.gov/argoapi"
export ANTHROPIC_AUTH_TOKEN="your-argo-auth-id-here"
```

</details>

<details>
<summary>Using Argonne inference service (optional)</summary>

If you have an ALCF account, you can use Argonne inference service instead of OpenAI.

Authenticate via Globus to obtain ALCF inference token:

```bash
pip install openai globus_sdk
wget https://raw.githubusercontent.com/argonne-lcf/inference-endpoints/main/inference_auth_token.py
python inference_auth_token.py authenticate  # Enter globus authentication when prompted.
```

Set environment variables for ALCF Inference service and model. Obtain API Key:

```bash
export OPENAI_BASE_URL=https://inference-api.alcf.anl.gov/resource_server/metis/api/v1
export LLM_MODEL=gpt-oss-120b
export OPENAI_API_KEY=$(python inference_auth_token.py get_access_token)
```

</details>

Please report (e.g., via Issues or [support options](https://libensemble.readthedocs.io/en/main/introduction.html#resources)) if you have a KEY setup that does not work with the agent.


## Setup

The example script generator uses an application which can easily be built.

```bash
cd tests/six_hump_camel/
gcc six_hump_camel.c -o six_hump_camel.x -l
cd ../../
```

Note that six_hump_camel is used in many libEnsemble examples directly in Python, but
an MPI application is used to demonstrate running ensembles with a user application.

## Usage

The easiest way to try out is via the web UI interface in `web_ui/`.

Note that the web UI will inherit any environment (e.g. conda) you are in.

```bash
pip install fastapi uvicorn[standard] gradio websockets
cd web_ui
python gradio_ui.py
```

Click on the URL shown in the terminal to open the web interface.

In the interface press the `Start Agent` button.

See [web_ui/README.md](web_ui/README.md) for further details.

To run scripts on command line, some examples...

```bash
# Fix existing scripts (does not use six_hump_camel.x)
python ensemble_agent.py --scripts tests/scripts_with_errors/

# To run with script generation pre-filled prompt
python ensemble_agent.py

# Generate scripts interactively
python ensemble_agent.py --interactive

# Generate from a prompt
python ensemble_agent.py --prompt "Create APOSMM scripts..."

# Enable debug logging
python ensemble_agent.py --debug
```

Scripts are saved to `generated_scripts/` directory.

Scripts will be ran, fixes attempted on failure, and reran.

Each time scripts are modified by the agent a version will be stored under `generated_scripts/versions`.

When the agent is re-started any existing `generated_scripts/` directory is backed up
to an `archive_runs/` dir.


## Options

To see all script options run

```bash
python ensemble_agent.py -h
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

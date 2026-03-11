# Ensemble Agent

An agentic system for generating, running, and iteratively fixing simulation scripts. Currently supports [libEnsemble](https://github.com/Libensemble/libensemble), designed to extend to other ensemble tools.

Uses LangChain ReAct agents with tools exposed via MCP and local Python functions.

## Installation

Dependencies (no package installer yet):

    pip install langchain langchain-openai langchain-anthropic langchain-mcp-adapters mcp matplotlib

For the web UI:

    pip install gradio fastapi uvicorn[standard] websockets

## MCP Server Setup (Script Generation)

The script generator runs as an MCP server from a separate repository.
It is **not** requied when user scripts are specified via `--scripts` option.

```bash
sudo apt install nodejs
git clone https://github.com/Libensemble/script-creator.git
cd script-creator
export GENERATOR_MCP_SERVER="$(pwd)/mcp_server.mjs"
npm install
```

## Options for LLM model keys

For all workflows, you will need a key to access an LLM.

For example, you can set an OpenAPI key.
Requires an [OpenAI account](https://platform.openai.com).
Make sure to check the MODEL and usage rates.

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

See [Model comparison](#model-comparison) below for model performance analysis.

### Using other LLM services

<details>
<summary>Using Argo gateway (optional)</summary>

If you have access to Argo at Argonne, you can use it to access Claude and/or OpenAI models.

For Claude models:

```bash
export ANTHROPIC_BASE_URL="https://apps-dev.inside.anl.gov/argoapi"
export ANTHROPIC_API_KEY="your-anl-username"
```

For OpenAI models:

```bash
export OPENAI_BASE_URL="https://apps-dev.inside.anl.gov/argoapi/v1"
export OPENAI_API_KEY="your-anl-username"
```

Set both if you want access to both model families.

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

Please [report](#support) if you have a KEY setup that does not work with the agent.


## Setup

The example script generator uses an application which can easily be built.

```bash
cd tests/six_hump_camel/
gcc six_hump_camel.c -o six_hump_camel.x -l
cd ../../
```

Note that six_hump_camel is used in many libEnsemble examples directly in Python, but
an MPI application is used to demonstrate running ensembles with a user application.

## Running Agent (Web UI)

The easiest way to try out is via the web UI interface in `web_ui/`.

*Note that the web UI will inherit any environment (e.g. conda) you are in.*

```bash
cd web_ui
python gradio_ui.py
```

Click on the URL shown in the terminal to open the web interface.

In the interface press the `Start Agent` button.

See [web_ui/README.md](web_ui/README.md) for further details.

## Running Agent (command line)

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

A user run script can also be run directly using the agent, however as there
is not yet an installable agent package it must be run from the base `ensemble_agent/`
directory.

```bash
python -m ensemble_agent tests/scripts_with_errors/run_example.py
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
| `OPENAI_BASE_URL` | Custom OpenAI-compatible endpoint |
| `ANTHROPIC_BASE_URL` | Custom Anthropic endpoint |
| `LLM_MODEL` | Override default model |
| `GENERATOR_MCP_SERVER` | Path to `mcp_server.mjs` |
| `AGENT_DEBUG` | Enable debug logging |


## Model comparison

As of March 9 2026, the model used primarily in testing has been Claude Opus 4.6.
Opus shows significantly better script fixing than Haiku, and slight benefits
over Sonnet (both at 4.6).

For example, the initial script generation from templates brings in a script
using Scipy neldermead optimizer. Using the default prompt which requests an
"optimizer that is good for smooth functions", Opus and Sonnet convert to using
`nlopt` with "LN_BOBYQA", which is indicated in the reference docs. Haiku did
not change the optimizer. Opus had minor configuration details over Sonnet and
presented a more detailed analysis (e.g., table of minima found).

The Opus and Sonnet scripts both ran first time and produced good output.

**Recommendation**: For Claude, use Sonnet or Opus (comparison with v4.6).

OpenAI models:

GPT-5.4 produced correct scripts with and ran first time. It used `nlopt`
with "LN_BOBYQA".

GPT-5.2 used `nlopt` and the script ran first time, but did not add
`rk_const`, and found minima slower.

GPT-5.1 did not change the optimizer from the template default.

**Recommendation**: For OpenAI, use GPT-5.4+ (GPT-5.2 is usable).

## Support

Please report issues or suggestions via Issues or [support options](https://libensemble.readthedocs.io/en/main/introduction.html#resources)

# Web UI for libEnsemble Agents

Web interface for running libEnsemble agent scripts with real-time output and script viewing.

## Installation

Install the required dependencies:

```bash
pip install fastapi uvicorn[standard] gradio websockets
```

This is in addition to any dependencies required for running the scripts.

## Usage

### Quick Start

The following assumes an API KEY is set in the environment. The interface
will pick up available models.

Start the gradio web server (from web_ui dir):

```bash
python gradio_ui.py
```

Click on the URL shown in the terminal to open the web interface.

### Use the Web Interface

1. **Select Agent Script**: Choose which agent script to run (e.g., `libe_agent_basic.py`)
2. **Select Scripts Directory**: Choose the test directory containing scripts to process (e.g., scripts_with_errors).
3. **Click Run**: The agent will execute and output will appear in real-time
4. **View Generated Scripts**: Generated scripts will appear in the dropdown and can be viewed

For interactive scripts, you can enter prompts when the agent needs user input.

## Directory Structure

- `app.py` - FastAPI WebSocket server backend
- `gradio_ui.py` - Gradio web interface frontend
- Agent entry point (`ensemble_agent.py`) should be in the project root (parent of `web_ui/`)
- Test script directories should be in `tests/`

## Advanced: Separate Terminals

If you prefer to run the components separately (useful for debugging):

**Terminal 1** - Start the WebSocket server (from web_ui dir):
```bash
uvicorn app:app --reload --port 8000
```

**Terminal 2** - Start the Gradio interface (from web_ui dir):
```bash
python gradio_ui.py
```
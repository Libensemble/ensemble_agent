import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from queue import Queue, Empty

import gradio as gr
import requests
import websockets

sys.path.insert(0, str(Path(__file__).parent.parent))
from ensemble_agent.config import DEFAULT_OUTPUT_DIR, _default_model

WS_URL = "ws://127.0.0.1:8000/ws/test"
DEFAULT_AGENT_DIR = Path(__file__).parent.parent
ALCF_API_BASE = "https://inference-api.alcf.anl.gov"
ALCF_ENDPOINTS_URL = f"{ALCF_API_BASE}/resource_server/list-endpoints"


def _fetch_models():
    """Fetch available models from all configured services.
    Supports ALCF, OpenAI-compatible, and Anthropic endpoints.
    Returns (choices, model_map, error_or_none).
    model_map: label -> (model_name, base_url)
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("ANTHROPIC_AUTH_TOKEN", "")
    anthropic_base = os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
    base_url = os.environ.get("OPENAI_BASE_URL", "")

    if not api_key and not anthropic_key:
        return [], {}, "No API keys set (OPENAI_API_KEY or ANTHROPIC_API_KEY)"

    choices = []
    model_map = {}
    errors = []

    # --- OpenAI / ALCF ---
    if api_key:
        if "alcf" in base_url.lower():
            try:
                resp = requests.get(
                    ALCF_ENDPOINTS_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=10,
                )
                if resp.status_code in (401, 403):
                    errors.append("ALCF: auth failed — token may be expired")
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    skip = {"embed", "genslm"}
                    for cluster, info in data.get("clusters", {}).items():
                        for fw_name, fw in info.get("frameworks", {}).items():
                            if "/v1/chat/completions" not in fw.get("endpoints", []):
                                continue
                            cluster_url = f"{ALCF_API_BASE}{info['base_url']}/{fw_name}/v1"
                            for model in fw.get("models", []):
                                if any(s in model.lower() for s in skip):
                                    continue
                                label = f"{model} ({cluster})"
                                choices.append(label)
                                model_map[label] = (model, cluster_url)
            except requests.RequestException as e:
                errors.append(f"Cannot reach ALCF API: {e}")
        else:
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=base_url or None)
                models = client.models.list()
                source = "OpenAI" if not base_url else base_url.split("//")[-1].split("/")[0]
                skip = {"embed", "tts", "whisper", "dall-e", "davinci", "babbage", "moderation"}
                for m in sorted(models.data, key=lambda x: x.id):
                    if any(s in m.id.lower() for s in skip):
                        continue
                    label = f"{m.id} ({source})"
                    choices.append(label)
                    model_map[label] = (m.id, base_url)
            except Exception as e:
                msg = str(e)
                if "401" in msg or "invalid" in msg.lower() or "api key" in msg.lower():
                    errors.append("OpenAI: invalid API key")
                else:
                    errors.append(f"OpenAI: cannot fetch models ({type(e).__name__})")

    # --- Anthropic (or Argo when ANTHROPIC_BASE_URL set) ---
    if anthropic_key:
        try:
            url = f"{anthropic_base.rstrip('/')}/v1/models?limit=100"
            resp = requests.get(
                url,
                headers={
                    "x-api-key": anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=10,
            )
            if resp.status_code in (401, 403):
                errors.append("Anthropic: auth failed — check ANTHROPIC_API_KEY")
            else:
                resp.raise_for_status()
                data = resp.json()
                service_name = "Argo" if os.environ.get("ANTHROPIC_BASE_URL") else "Anthropic"
                for m in sorted(data.get("data", []), key=lambda x: x.get("id", "")):
                    mid = m.get("id", "")
                    label = f"{mid} ({service_name})"
                    choices.append(label)
                    model_map[label] = (mid, "")
        except requests.RequestException as e:
            errors.append(f"Anthropic: cannot fetch models ({e})")

    if not choices and errors:
        return [], {}, "; ".join(errors)
    if errors:
        for e in errors:
            print(f"⚠ Model fetch: {e}")
    return sorted(choices), model_map, None


def _current_model_label():
    """Label for the currently configured model."""
    model = _default_model()
    base = os.environ.get("OPENAI_BASE_URL", "")
    if "claude" in model.lower():
        return f"{model} (Argo)" if os.environ.get("ANTHROPIC_BASE_URL") else f"{model} (Anthropic)"
    if "metis" in base:
        return f"{model} (metis)"
    elif "sophia" in base:
        return f"{model} (sophia)"
    elif "alcf" in base.lower():
        return f"{model} (alcf)"
    elif base:
        return f"{model} (custom)"
    return f"{model} (OpenAI)"


def _check_api(model=None, base_url=None):
    """Quick API check. Returns None on success, or an error message string."""
    model = model or _default_model()
    base_url = base_url or os.environ.get("OPENAI_BASE_URL")

    if "claude" in model.lower():
        api_key = os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return "⚠️ ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN required for Claude."
        base = os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com"
        try:
            resp = requests.post(
                f"{base.rstrip('/')}/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
                timeout=15,
            )
            if resp.ok:
                return None
            if resp.status_code in (401, 403):
                return "⚠️ Anthropic auth failed. Check ANTHROPIC_API_KEY."
            return f"⚠️ Anthropic API check failed ({model}): {resp.status_code}"
        except Exception as e:
            return f"⚠️ Anthropic API check failed: {e}"

    from openai import OpenAI
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), base_url=base_url)
        client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "hi"}], max_tokens=1
        )
        return None
    except Exception as e:
        msg = str(e)
        if "403" in msg or "Permission" in msg.lower():
            return ("⚠️ API auth failed. Token likely expired.\n\n"
                    "```\npython3 inference_auth_token.py authenticate --force\n"
                    "export OPENAI_API_KEY=$(python inference_auth_token.py get_access_token)\n```\n\n"
                    "Then restart the UI.")
        elif "401" in msg or "invalid" in msg.lower():
            return f"⚠️ Invalid API key for {model}. Check OPENAI_API_KEY."
        else:
            return f"⚠️ API check failed ({model}): {e}"


DEFAULT_TESTS_DIR = DEFAULT_AGENT_DIR / "tests"
DEFAULT_AGENT_PATTERN = "ensemble_agent.py"
NONE_OPTION = "None (generate scripts)"
INPUT_MARKER = "[INPUT_REQUESTED]"

ws_conn = None
message_queue = Queue()
output_queue = Queue()
ws_thread = None
stop_event = threading.Event()
uvicorn_process = None


def scan_agent_scripts(agent_dir_path, pattern=None):
    if pattern is None:
        pattern = DEFAULT_AGENT_PATTERN
    try:
        if not agent_dir_path:
            return []
        agent_dir = Path(agent_dir_path)
        if not agent_dir.exists():
            return []
        exclude = {"app.py", "gradio_ui.py", "__init__.py"}
        return [f.name for f in sorted(agent_dir.glob(pattern)) if f.name not in exclude]
    except Exception:
        return []


def scan_script_dirs(scripts_dir_path):
    try:
        if not scripts_dir_path:
            return [NONE_OPTION]
        scripts_dir = Path(scripts_dir_path)
        if not scripts_dir.exists():
            return [NONE_OPTION]
        dirs = [d.name for d in sorted(scripts_dir.iterdir()) if d.is_dir() and not d.name.startswith("_")]
        return [NONE_OPTION] + dirs
    except Exception:
        return [NONE_OPTION]


def scan_versions(agent_dir_path):
    try:
        if not agent_dir_path:
            return ["latest"]
        versions_dir = Path(agent_dir_path) / DEFAULT_OUTPUT_DIR / "versions"
        if not versions_dir.exists():
            return ["latest"]
        return ["latest"] + [d.name for d in sorted(versions_dir.iterdir(), reverse=True)
                             if d.is_dir() and not d.name.startswith("_")]
    except Exception:
        return ["latest"]


def websocket_worker():
    global ws_conn
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run():
        global ws_conn
        try:
            ws_conn = await websockets.connect(WS_URL)
            output_queue.put(("status", "connected"))
            while not stop_event.is_set():
                try:
                    msg_to_send = message_queue.get_nowait()
                    await ws_conn.send(msg_to_send)
                except Empty:
                    pass
                try:
                    raw = await asyncio.wait_for(ws_conn.recv(), timeout=0.1)
                    output_queue.put(("message", raw))
                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    output_queue.put(("error", "Websocket connection closed"))
                    break
            if ws_conn:
                await ws_conn.close()
        except Exception as e:
            output_queue.put(("error", f"Websocket error: {e}"))

    loop.run_until_complete(_run())
    loop.close()


# Initial scan
_init_agents = scan_agent_scripts(str(DEFAULT_AGENT_DIR))
_init_tests = scan_script_dirs(str(DEFAULT_TESTS_DIR))
_init_versions = scan_versions(str(DEFAULT_AGENT_DIR))

# Determine service label for title
_cur_base = os.environ.get("OPENAI_BASE_URL", "")
_has_openai = bool(os.environ.get("OPENAI_API_KEY"))
_has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
if "alcf" in _cur_base.lower():
    _service_label = "ALCF"
elif _cur_base:
    _service_label = _cur_base.split("//")[-1].split("/")[0]
elif _has_openai:
    _service_label = "OpenAI"
else:
    _service_label = ""
if _has_anthropic:
    _argo = "Argo" if os.environ.get("ANTHROPIC_BASE_URL") else "Anthropic"
    _service_label = f"{_service_label} + {_argo}" if _service_label else _argo

# Fetch available models (one quick call at startup)
_init_model_label = _current_model_label()
_cur_model = _default_model()
_init_model_choices, _init_model_map, _init_model_err = _fetch_models()
if _init_model_label not in _init_model_map:
    _init_model_choices = [_init_model_label] + _init_model_choices
    _init_model_map[_init_model_label] = (_cur_model, _cur_base)
if not _init_model_choices:
    _init_model_choices = [_init_model_label]
if _init_model_err:
    print(f"⚠ Model fetch: {_init_model_err}")
    print(f"  Check API keys (OPENAI_API_KEY / ANTHROPIC_API_KEY) and OPENAI_BASE_URL.")

with gr.Blocks() as demo:
    with gr.Row():
        gr.Markdown(f"### libEnsemble Agent &nbsp; · &nbsp; Service: `{_service_label}`")
        run_btn = gr.Button("Start Agent", variant="primary")
        reset_btn = gr.Button("Reset", variant="stop")
        settings_btn = gr.Button("⚙️")

    agent_dir_state = gr.State(value=str(DEFAULT_AGENT_DIR))
    scripts_dir_state = gr.State(value=str(DEFAULT_TESTS_DIR))
    agent_pattern_state = gr.State(value=DEFAULT_AGENT_PATTERN)
    model_map_state = gr.State(value=_init_model_map)
    settings_visible = gr.State(value=False)

    with gr.Column(visible=False) as settings_modal:
        with gr.Column(elem_classes="modal-content"):
            gr.Markdown("### Settings")
            agent_dir_input = gr.Textbox(label="Agent Directory", value=str(DEFAULT_AGENT_DIR))
            scripts_dir_input = gr.Textbox(label="Scripts Parent Directory", value=str(DEFAULT_TESTS_DIR))
            agent_pattern_input = gr.Textbox(label="Agent Script Pattern", value=DEFAULT_AGENT_PATTERN)
            mcp_tools_checkbox = gr.Checkbox(label="Use FastMCP tool server (--mcp-tools)", value=False)
            with gr.Row():
                apply_settings_btn = gr.Button("Apply", variant="primary", size="sm")
                close_settings_btn = gr.Button("Close", size="sm")

    with gr.Row():
        agent_dropdown = gr.Dropdown(
            label="Agent Script", choices=_init_agents,
            value=_init_agents[0] if _init_agents else None,
            allow_custom_value=True, scale=2
        )
        scripts_dropdown = gr.Dropdown(
            label="Scripts Directory", choices=_init_tests,
            value=NONE_OPTION, allow_custom_value=True, scale=2
        )
        model_dropdown = gr.Dropdown(
            label="Model", choices=_init_model_choices, value=_init_model_label,
            allow_custom_value=True, scale=2, min_width=300
        )

    chatbot = gr.Chatbot(label="Agent", height=400)
    with gr.Row():
        chat_input = gr.Textbox(
            placeholder="Type prompt or response here...",
            show_label=False, scale=4, lines=1
        )
        send_btn = gr.Button("Send", scale=0, min_width=80)

    with gr.Tabs():
        with gr.Tab("Scripts"):
            version_dropdown = gr.Dropdown(
                label="libE scripts", choices=_init_versions, value="latest"
            )
            script_file_dropdown = gr.Dropdown(label="Generated Scripts", choices=[], value=None)
            output_script = gr.Code(label="Script Content", language="python", lines=10)
        with gr.Tab("Graphs"):
            graphs_refresh_btn = gr.Button("Refresh Graphs", size="sm")
            graphs_gallery = gr.Gallery(
                label="Generated Graphs", columns=1, height="auto",
                object_fit="scale-down", show_label=False, preview=True
            )
        with gr.Tab("Debug Log"):
            debug_refresh_btn = gr.Button("Refresh Log", size="sm")
            debug_log_box = gr.Code(label="Agent Debug Log", language=None, lines=20)

    # --- Helpers ---

    def _drain_queue(q):
        while not q.empty():
            try:
                q.get_nowait()
            except Empty:
                break

    def start_websocket():
        global ws_thread
        if ws_thread is None or not ws_thread.is_alive():
            stop_event.clear()
            ws_thread = threading.Thread(target=websocket_worker, daemon=True)
            ws_thread.start()

    # --- Core event handlers ---

    def _input_disabled(placeholder="Agent is working..."):
        return gr.update(interactive=False, placeholder=placeholder), gr.update(interactive=False)

    def _input_enabled(placeholder="Type your response..."):
        return gr.update(interactive=True, placeholder=placeholder), gr.update(interactive=True)

    def start_run(agent_script, scripts_dir, history, agent_dir_val, scripts_dir_val,
                  model_label, model_map, mcp_tools):
        """Send run command and add user message to chat"""
        if not agent_script:
            history = history + [{"role": "assistant", "content": "⚠️ No agent script selected"}]
            return history, *_input_enabled("Type prompt or response here...")

        # Resolve model from dropdown selection
        if model_label and model_label in model_map:
            sel_model, sel_base_url = model_map[model_label]
        else:
            sel_model = _default_model()
            sel_base_url = os.environ.get("OPENAI_BASE_URL", "")

        # Preflight API check with selected model
        api_err = _check_api(model=sel_model, base_url=sel_base_url or None)
        if api_err:
            history = history + [{"role": "assistant", "content": api_err}]
            return history, *_input_enabled("Type prompt or response here...")

        agent_dir = Path(agent_dir_val) if agent_dir_val else DEFAULT_AGENT_DIR
        scripts_base = Path(scripts_dir_val) if scripts_dir_val else DEFAULT_TESTS_DIR

        resolved = None
        if scripts_dir and scripts_dir != NONE_OPTION:
            resolved = str(scripts_base / scripts_dir) if not Path(scripts_dir).is_absolute() else scripts_dir

        # Show what we're running
        cmd_desc = f"▶ {agent_script}"
        if resolved:
            cmd_desc += f" --scripts {Path(resolved).name}"
        history = history + [{"role": "user", "content": cmd_desc}]

        _drain_queue(output_queue)

        if not ws_thread or not ws_thread.is_alive():
            history = history + [{"role": "assistant", "content": "⚠️ Websocket not connected. Try refreshing."}]
            return history, *_input_enabled("Type prompt or response here...")

        message_queue.put(json.dumps({
            "type": "run",
            "agent_script": agent_script,
            "scripts_dir": resolved,
            "agent_dir": str(agent_dir),
            "llm_model": sel_model,
            "openai_base_url": sel_base_url,
            "mcp_tools": bool(mcp_tools),
        }))
        return history, *_input_disabled()

    def stream_output(history):
        """Stream script output as assistant messages. Stops when input is requested or script finishes."""
        history = history + [{"role": "assistant", "content": ""}]
        start = time.time()
        timeout = 300
        disabled = _input_disabled()

        while (time.time() - start) < timeout:
            try:
                msg_type, data = output_queue.get(timeout=0.2)

                if msg_type == "message":
                    msg = json.loads(data)
                    if msg["type"] == "log":
                        text = msg["text"]

                        # Check for input marker — stop streaming, let user respond
                        if INPUT_MARKER in text:
                            clean = text.replace(INPUT_MARKER, "").strip()
                            if clean:
                                history[-1]["content"] += clean + "\n"
                            yield history, *_input_enabled()
                            return

                        history[-1]["content"] += text + "\n"
                        yield history, *disabled

                        if text.startswith("done:") or text.startswith("stopped"):
                            yield history, *_input_disabled("Agent finished. Start a new run or reset.")
                            return

                elif msg_type == "error":
                    history[-1]["content"] += f"⚠️ {data}\n"
                    yield history, *_input_enabled("Type prompt or response here...")
                    return

                elif msg_type == "status":
                    # Connection status etc - skip
                    pass

            except Empty:
                yield history, *disabled

    def send_user_input(text, history):
        """Send user response to the running script's stdin"""
        user_text = text.strip() if text else ""
        message_queue.put(json.dumps({"type": "input", "text": user_text}))
        if user_text:
            history = history + [{"role": "user", "content": user_text}]
        else:
            history = history + [{"role": "user", "content": "↵"}]
        return gr.update(value="", interactive=False, placeholder="Agent is working..."), history, gr.update(interactive=False)

    # --- Settings handlers ---

    def toggle_settings(current_visible):
        return not current_visible, gr.update(visible=not current_visible)

    def apply_settings(agent_dir, agent_pattern, scripts_dir):
        new_agent_dir = agent_dir.strip() if agent_dir and agent_dir.strip() else str(DEFAULT_AGENT_DIR)
        new_agent_pattern = agent_pattern.strip() if agent_pattern and agent_pattern.strip() else DEFAULT_AGENT_PATTERN
        new_scripts_dir = scripts_dir.strip() if scripts_dir and scripts_dir.strip() else str(DEFAULT_TESTS_DIR)
        return (
            new_agent_dir, new_agent_pattern, new_scripts_dir,
            gr.update(choices=scan_agent_scripts(new_agent_dir, new_agent_pattern),
                      value=scan_agent_scripts(new_agent_dir, new_agent_pattern)[0]
                      if scan_agent_scripts(new_agent_dir, new_agent_pattern) else None),
            gr.update(choices=scan_script_dirs(new_scripts_dir), value=NONE_OPTION),
            gr.update(choices=scan_versions(new_agent_dir), value="latest"),
            False, gr.update(visible=False)
        )

    # --- Scripts panel handlers ---

    def load_version_scripts(version, agent_dir_val):
        agent_dir = Path(agent_dir_val) if agent_dir_val else DEFAULT_AGENT_DIR
        if version and version != "latest":
            scripts_dir = agent_dir / DEFAULT_OUTPUT_DIR / "versions" / version
        else:
            scripts_dir = agent_dir / DEFAULT_OUTPUT_DIR

        scripts = {}
        if scripts_dir.exists():
            for f in sorted(scripts_dir.glob("*.py")):
                scripts[f.name] = f.read_text()

        names = list(scripts.keys())
        selected = names[0] if names else None
        return scripts, gr.update(choices=names, value=selected), scripts.get(selected, "") if selected else ""

    def update_script_display(selected_name, scripts_state):
        if selected_name and selected_name in scripts_state:
            return scripts_state[selected_name]
        return ""

    def refresh_versions(agent_dir_val):
        return gr.update(choices=scan_versions(agent_dir_val))

    def fetch_debug_log(agent_dir_val):
        try:
            resp = requests.get(
                "http://127.0.0.1:8000/debug-log",
                params={"agent_dir": agent_dir_val or str(DEFAULT_AGENT_DIR)},
                timeout=3,
            )
            if resp.ok:
                return resp.json().get("content", "")
        except Exception:
            pass
        return "(no debug log available)"

    def load_graphs(agent_dir_val):
        agent_dir = Path(agent_dir_val) if agent_dir_val else DEFAULT_AGENT_DIR
        graphs_dir = agent_dir / DEFAULT_OUTPUT_DIR / "graphs"
        if not graphs_dir.exists():
            return []
        pngs = sorted(graphs_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(p) for p in pngs]

    def reset_ui():
        message_queue.put(json.dumps({"type": "stop"}))
        _drain_queue(output_queue)
        _drain_queue(message_queue)
        return [], gr.update(choices=[], value=None), "", *_input_enabled("Type prompt or response here...")

    scripts_dict = gr.State(value={})

    # --- Wire up events ---

    demo.load(start_websocket)

    # Settings
    settings_btn.click(toggle_settings, inputs=[settings_visible], outputs=[settings_visible, settings_modal])
    close_settings_btn.click(lambda: (False, gr.update(visible=False)), outputs=[settings_visible, settings_modal])
    apply_settings_btn.click(
        apply_settings,
        inputs=[agent_dir_input, agent_pattern_input, scripts_dir_input],
        outputs=[agent_dir_state, agent_pattern_state, scripts_dir_state,
                 agent_dropdown, scripts_dropdown, version_dropdown,
                 settings_visible, settings_modal]
    )

    # Run button: start script → stream output → refresh versions → load scripts → refresh graphs → refresh debug log
    run_btn.click(
        start_run,
        inputs=[agent_dropdown, scripts_dropdown, chatbot, agent_dir_state, scripts_dir_state,
                model_dropdown, model_map_state, mcp_tools_checkbox],
        outputs=[chatbot, chat_input, send_btn]
    ).then(
        stream_output, inputs=[chatbot], outputs=[chatbot, chat_input, send_btn]
    ).then(
        refresh_versions, inputs=[agent_dir_state], outputs=[version_dropdown]
    ).then(
        load_version_scripts, inputs=[version_dropdown, agent_dir_state],
        outputs=[scripts_dict, script_file_dropdown, output_script]
    ).then(
        load_graphs, inputs=[agent_dir_state], outputs=[graphs_gallery]
    ).then(
        fetch_debug_log, inputs=[agent_dir_state], outputs=[debug_log_box]
    )

    # Chat input: send to stdin → stream continued output
    send_btn.click(
        send_user_input, inputs=[chat_input, chatbot],
        outputs=[chat_input, chatbot, send_btn]
    ).then(
        stream_output, inputs=[chatbot], outputs=[chatbot, chat_input, send_btn]
    ).then(
        refresh_versions, inputs=[agent_dir_state], outputs=[version_dropdown]
    ).then(
        load_version_scripts, inputs=[version_dropdown, agent_dir_state],
        outputs=[scripts_dict, script_file_dropdown, output_script]
    ).then(
        load_graphs, inputs=[agent_dir_state], outputs=[graphs_gallery]
    ).then(
        fetch_debug_log, inputs=[agent_dir_state], outputs=[debug_log_box]
    )
    chat_input.submit(
        send_user_input, inputs=[chat_input, chatbot],
        outputs=[chat_input, chatbot, send_btn]
    ).then(
        stream_output, inputs=[chatbot], outputs=[chatbot, chat_input, send_btn]
    ).then(
        refresh_versions, inputs=[agent_dir_state], outputs=[version_dropdown]
    ).then(
        load_version_scripts, inputs=[version_dropdown, agent_dir_state],
        outputs=[scripts_dict, script_file_dropdown, output_script]
    ).then(
        load_graphs, inputs=[agent_dir_state], outputs=[graphs_gallery]
    ).then(
        fetch_debug_log, inputs=[agent_dir_state], outputs=[debug_log_box]
    )

    # Reset
    reset_btn.click(reset_ui, outputs=[chatbot, script_file_dropdown, output_script, chat_input, send_btn])

    # Scripts panel
    script_file_dropdown.change(update_script_display, inputs=[script_file_dropdown, scripts_dict], outputs=output_script)
    version_dropdown.change(load_version_scripts, inputs=[version_dropdown, agent_dir_state], outputs=[scripts_dict, script_file_dropdown, output_script])

    # Graphs
    graphs_refresh_btn.click(load_graphs, inputs=[agent_dir_state], outputs=[graphs_gallery])

    # Debug log
    debug_refresh_btn.click(fetch_debug_log, inputs=[agent_dir_state], outputs=[debug_log_box])


def start_uvicorn_server():
    global uvicorn_process
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 8000))
        sock.close()
        if result == 0:
            print("✓ Uvicorn server already running on port 8000")
            return
    except:
        pass

    print("Starting uvicorn server...")
    uvicorn_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--reload", "--port", "8000"],
        cwd=str(Path(__file__).parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    max_wait = 3
    waited = 0
    while waited < max_wait:
        if uvicorn_process.poll() is not None:
            print("✗ Failed to start uvicorn server")
            stderr = uvicorn_process.stderr.read().decode() if uvicorn_process.stderr else ""
            print(f"Error: {stderr}")
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', 8000))
        sock.close()
        if result == 0:
            print("✓ Uvicorn server started on port 8000")
            return
        time.sleep(0.5)
        waited += 0.5

    print("⚠ Uvicorn server may not be ready yet (timeout)")


if __name__ == "__main__":
    start_uvicorn_server()
    print("Starting Gradio interface...")
    demo.launch(allowed_paths=[str(DEFAULT_AGENT_DIR / DEFAULT_OUTPUT_DIR)])

    if uvicorn_process:
        print("\nStopping uvicorn server...")
        uvicorn_process.terminate()
        uvicorn_process.wait()

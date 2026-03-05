import asyncio
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from queue import Queue, Empty

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

sys.path.insert(0, str(Path(__file__).parent.parent))
from ensemble_agent.config import DEFAULT_OUTPUT_DIR

app = FastAPI()

AGENT_DIR = Path(__file__).parent.parent
GENERATED_SCRIPTS_DIR = AGENT_DIR / DEFAULT_OUTPUT_DIR


class Session:
    def __init__(self):
        self.output_queue = Queue()
        self.process = None

    async def _send(self, ws, msg):
        await ws.send_text(json.dumps(msg))

    async def _log(self, ws, text):
        await self._send(ws, {"type": "log", "text": text})

    async def _send_scripts(self, ws):
        if not GENERATED_SCRIPTS_DIR.exists():
            return
        for f in sorted(GENERATED_SCRIPTS_DIR.glob("*.py")):
            await self._send(ws, {
                "type": "script",
                "filename": f.name,
                "content": f.read_text()
            })

    def send_input(self, text):
        """Send text to the running process's stdin (flattened to one line for input())"""
        if self.process and self.process.stdin:
            try:
                single_line = text.replace("\n", " ").replace("\r", " ")
                self.process.stdin.write(single_line + "\n")
                self.process.stdin.flush()
            except Exception as e:
                self.output_queue.put(("error", f"Failed to send input: {e}"))

    def _subprocess_thread(self, cmd, cwd, env_overrides=None):
        try:
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            if env_overrides:
                env.update(env_overrides)
            self.process = subprocess.Popen(
                cmd,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
            )
            for line in self.process.stdout:
                self.output_queue.put(("line", line.rstrip()))
            self.process.wait()
            self.output_queue.put(("exit", self.process.returncode))
        except Exception as e:
            self.output_queue.put(("error", str(e)))
        finally:
            self.process = None

    async def run_agent(self, agent_script, scripts_dir, ws, agent_dir=None,
                        llm_model=None, openai_base_url=None):
        run_dir = Path(agent_dir) if agent_dir else AGENT_DIR
        cmd = [sys.executable, agent_script]

        if scripts_dir:
            cmd.extend(["--scripts", scripts_dir])
        else:
            cmd.append("--interactive")

        await self._log(ws, f"started: {' '.join(cmd)}")

        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break

        env_overrides = {"AGENT_DEBUG": "1"}
        if llm_model:
            env_overrides["LLM_MODEL"] = llm_model
        if openai_base_url:
            env_overrides["OPENAI_BASE_URL"] = openai_base_url

        thread = threading.Thread(
            target=self._subprocess_thread,
            args=(cmd, str(run_dir)),
            kwargs={"env_overrides": env_overrides or None},
            daemon=True
        )
        thread.start()

        done = False
        while not done:
            try:
                msg_type, data = self.output_queue.get_nowait()
                if msg_type == "line":
                    await self._log(ws, data)
                    if "Saved:" in data:
                        await self._send_scripts(ws)
                elif msg_type == "exit":
                    await self._log(ws, f"\nProcess exited with code {data}")
                    await self._send_scripts(ws)
                    done = True
                elif msg_type == "error":
                    await self._log(ws, f"Error: {data}")
                    done = True
            except Empty:
                await asyncio.sleep(0.1)

        await self._log(ws, "done: complete")


sessions: dict[str, Session] = {}


@app.get("/graphs")
async def list_graphs(agent_dir: str = ""):
    run_dir = Path(agent_dir) if agent_dir else AGENT_DIR
    graphs_dir = run_dir / DEFAULT_OUTPUT_DIR / "graphs"
    if not graphs_dir.exists():
        return {"graphs": []}
    pngs = sorted(
        [f.name for f in graphs_dir.glob("*.png")],
        key=lambda n: os.path.getmtime(graphs_dir / n),
        reverse=True,
    )
    return {"graphs": pngs}


@app.get("/graphs/{filename}")
async def serve_graph(filename: str, agent_dir: str = ""):
    run_dir = Path(agent_dir) if agent_dir else AGENT_DIR
    filepath = run_dir / DEFAULT_OUTPUT_DIR / "graphs" / filename
    if not filepath.exists() or not filepath.suffix == ".png":
        return {"error": "Not found"}
    return FileResponse(str(filepath), media_type="image/png")


@app.get("/debug-log")
async def get_debug_log(agent_dir: str = ""):
    run_dir = Path(agent_dir) if agent_dir else AGENT_DIR
    log_file = run_dir / DEFAULT_OUTPUT_DIR / "debug_log.txt"
    if log_file.exists():
        return {"content": log_file.read_text()}
    return {"content": ""}


@app.websocket("/ws/{session_id}")
async def ws_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()
    s = sessions.setdefault(session_id, Session())
    agent_task = None
    try:
        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            if msg.get("type") == "input":
                s.send_input(msg.get("text", ""))
            else:
                # Run agent as background task so we can keep receiving input
                if agent_task and not agent_task.done():
                    agent_task.cancel()
                agent_task = asyncio.create_task(
                    s.run_agent(
                        msg.get("agent_script", ""),
                        msg.get("scripts_dir") or "",
                        ws,
                        agent_dir=msg.get("agent_dir"),
                        llm_model=msg.get("llm_model"),
                        openai_base_url=msg.get("openai_base_url"),
                    )
                )
    except WebSocketDisconnect:
        if agent_task and not agent_task.done():
            agent_task.cancel()

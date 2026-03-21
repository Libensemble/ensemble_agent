#!/usr/bin/env python3
"""
Autonomous LangChain agent for running and fixing libEnsemble scripts.

This offers a demonstrator of a much simpler, standalone, agent.

For options: python fixup_agent.py -h
"""

import os
import sys
import asyncio
import subprocess
import argparse
import shutil
import time
from pathlib import Path
from langchain_core.tools import tool
from langchain.agents import create_agent


# LLM model to use — default depends on which API key is available
DEFAULT_OPENAI_MODEL = "gpt-5.4"
DEFAULT_ANTHROPIC_MODEL = "claude-opus-4-6"
if os.environ.get("LLM_MODEL"):
    MODEL = os.environ["LLM_MODEL"]
elif os.environ.get("OPENAI_API_KEY") or not os.environ.get("ANTHROPIC_API_KEY"):
    MODEL = DEFAULT_OPENAI_MODEL
else:
    MODEL = DEFAULT_ANTHROPIC_MODEL


AGENT_PROMPT = """Run the script '{run_script_name}'. If it fails, fix any obvious errors \
based on the error message and retry. If you don't know how to fix it, stop."""


class DebugLogger:
    """Writes a clean debug log showing the agent's prompt, tools, and tool calls."""

    def __init__(self, log_path, model=""):
        self.log_path = Path(log_path)
        with open(self.log_path, "w") as f:
            f.write(f"Debug log: {time.strftime('%Y-%m-%d %H:%M:%S')}  Model: {model}\n\n")

    def log_prompt_and_tools(self, prompt, tools):
        with open(self.log_path, "a") as f:
            f.write("PROMPT\n" + "=" * 60 + "\n")
            f.write(prompt + "\n\n")
            f.write("TOOL SCHEMAS\n" + "=" * 60 + "\n")
            for t in tools:
                f.write(f"\n{t.name}: {t.description}\n")
                schema = t.args_schema.model_json_schema()
                schema.pop("description", None)
                schema.pop("title", None)
                f.write(f"  {schema}\n")
            f.write("\n")


    def log_messages(self, messages):
        with open(self.log_path, "a") as f:
            f.write("AGENT CONVERSATION\n" + "=" * 60 + "\n")
            for msg in messages:
                role = type(msg).__name__
                f.write(f"\n--- {role} ---\n")
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        args = tc.get("args", {})
                        # Show args but truncate long values (e.g. file content)
                        short_args = {}
                        for k, v in args.items():
                            s = str(v)
                            short_args[k] = s if len(s) <= 80 else f"[{len(s)} chars]"
                        f.write(f"  -> {tc.get('name', '?')}({short_args})\n")
                if isinstance(msg.content, list):
                    text = " ".join(b["text"] for b in msg.content if b.get("type") == "text")
                else:
                    text = msg.content
                if text:
                    if len(text) > 300:
                        f.write(f"  {text[:300]}...\n")
                    else:
                        f.write(f"  {text}\n")
            f.write(f"\n{'=' * 60}\n")
        print(f"Debug log written to {self.log_path}")


def create_llm(model, temperature=0, base_url=None):
    """Create LLM — ChatAnthropic for Claude models, ChatOpenAI otherwise."""
    if "claude" in model.lower():
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            sys.exit("Error: pip install langchain-anthropic required for Claude models")
        kwargs = {"model": model, "temperature": temperature, "streaming": True}
        if base_url:
            kwargs["anthropic_api_url"] = base_url
        return ChatAnthropic(**kwargs)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, temperature=temperature, base_url=base_url)


# Working directory for scripts
WORK_DIR = None

# Archive counter for version tracking
ARCHIVE_COUNTER = 1

# Current archive name (scripts and their output go together)
CURRENT_ARCHIVE = None

# Directory where existing generated_scripts runs are moved (create if missing)
ARCHIVE_RUNS_DIR = "archive_runs"

# Files and directories to archive after each run
ARCHIVE_ITEMS = [
    "ensemble",           # libEnsemble output directory
    "ensemble.log",       # libEnsemble log file
    "libE_stats.txt",     # libEnsemble stats file
    "*.npy",              # NumPy arrays
    "*.pickle",           # Pickle files
]


def archive_existing_output_dir(output_dir, archive_parent=None):
    """If output_dir exists, move it to archive_parent/output_dir_<unique>, then create fresh output_dir."""
    output_dir = Path(output_dir)
    archive_dir = Path(archive_parent or ARCHIVE_RUNS_DIR)
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        return
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / f"{output_dir.name}_{hex(time.time_ns())[2:10]}"
    shutil.move(str(output_dir), str(dest))
    print(f"Moved existing {output_dir} to {dest}")
    output_dir.mkdir(parents=True, exist_ok=True)


def start_new_archive(action: str):
    """Start a new archive version (scripts + their output go together)"""
    global ARCHIVE_COUNTER, CURRENT_ARCHIVE
    CURRENT_ARCHIVE = f"{ARCHIVE_COUNTER}_{action}"
    archive_dir = WORK_DIR / "versions" / CURRENT_ARCHIVE
    archive_dir.mkdir(parents=True, exist_ok=True)
    ARCHIVE_COUNTER += 1
    print(f"[Archive] Started new version: {CURRENT_ARCHIVE}")


def archive_current_scripts():
    """Archive all current scripts to the current archive"""
    if CURRENT_ARCHIVE is None:
        return
    archive_dir = WORK_DIR / "versions" / CURRENT_ARCHIVE
    for script_file in WORK_DIR.glob("*.py"):
        shutil.copy(script_file, archive_dir / script_file.name)
    print(f"[Archive] Saved scripts to: {CURRENT_ARCHIVE}/")


def archive_run_output(error_msg: str):
    """Archive run output to the current archive (same dir as the scripts)"""
    if CURRENT_ARCHIVE is None:
        return
    archive_dir = WORK_DIR / "versions" / CURRENT_ARCHIVE
    output_dir = archive_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "error.txt").write_text(error_msg)
    for item in ARCHIVE_ITEMS:
        item_path = WORK_DIR / item
        if item_path.exists() and item_path.is_dir():
            shutil.copytree(str(item_path), str(output_dir / item), dirs_exist_ok=True)
            shutil.rmtree(str(item_path))
        else:
            for filepath in WORK_DIR.glob(item):
                if filepath.is_file():
                    shutil.copy(str(filepath), str(output_dir / filepath.name))
                    filepath.unlink()
    print(f"[Archive] Saved run output to: {CURRENT_ARCHIVE}/output/")


# --- Agent tools ---

@tool
async def run_script(script_name: str) -> str:
    """Run a Python script. Returns SUCCESS if it works, FAILED with error details if it fails."""
    script_path = WORK_DIR / script_name
    timeout_seconds = 300

    if not script_path.exists():
        msg = f"ERROR: Script '{script_name}' not found in {WORK_DIR}"
        print(f"\n{msg}\n")
        return msg

    print("\nRunning scripts...")

    try:
        result = subprocess.run(
            ["python", script_name],
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=timeout_seconds
        )

        if result.returncode == 0:
            print("✓ Script ran successfully")
            return f"SUCCESS: Script ran successfully.\nOutput:\n{result.stdout[:500]}"

        error_msg = f"Return code {result.returncode}\nStderr: {result.stderr}\nStdout: {result.stdout}"
        print(f"✗ Scripts failed with return code {result.returncode}")
        if result.stderr:
            print(f"Error summary: {result.stderr.strip().split(chr(10))[-1]}\n")
        archive_run_output(error_msg)
        return f"FAILED: Script failed with return code {result.returncode}\n\nStderr:\n{result.stderr}\n\nStdout:\n{result.stdout[:500]}"

    except subprocess.TimeoutExpired:
        msg = f"ERROR: Script timed out after {timeout_seconds} seconds"
        print(f"\n{msg}\n")
        return msg
    except Exception as e:
        msg = f"ERROR: {str(e)}"
        print(msg)
        return msg


@tool
async def read_file(filepath: str) -> str:
    """Read a file and return its contents. Use this to inspect scripts before fixing them."""
    file_path = WORK_DIR / filepath
    if not file_path.exists():
        return f"ERROR: File '{filepath}' not found"
    try:
        return file_path.read_text()
    except Exception as e:
        return f"ERROR reading file: {str(e)}"


@tool
async def write_file(filepath: str, content: str) -> str:
    """Write content to a file. Use this to fix scripts that have errors."""
    file_path = WORK_DIR / filepath
    try:
        file_path.write_text(content)
        start_new_archive("script_fix")
        archive_current_scripts()
        return f"SUCCESS: Wrote {len(content)} characters to {filepath}"
    except Exception as e:
        msg = f"ERROR writing file: {str(e)}"
        print(msg)
        return msg


@tool
async def list_files() -> str:
    """List all Python files in the working directory."""
    try:
        py_files = list(WORK_DIR.glob("*.py"))
        if not py_files:
            return "No Python files found"
        return "Python files:\n" + "\n".join([f"- {f.name}" for f in py_files])
    except Exception as e:
        return f"ERROR listing files: {str(e)}"


def setup_work_directory(scripts_dir: str) -> Path:
    """Copy scripts to working directory and archive initial version"""
    global WORK_DIR
    scripts_dir = Path(scripts_dir)
    archive_existing_output_dir("generated_scripts")
    work_dir = Path("generated_scripts")
    WORK_DIR = work_dir
    for script_file in scripts_dir.glob("*.py"):
        shutil.copy(script_file, work_dir)
        print(f"Copied: {script_file.name}")
    start_new_archive("copied_scripts")
    archive_current_scripts()
    return work_dir


async def main():
    global WORK_DIR

    parser = argparse.ArgumentParser(description="Autonomous agent to run and fix libEnsemble scripts")
    parser.add_argument("--scripts", required=True, help="Directory containing scripts to run")
    parser.add_argument("--max-iterations", type=int, default=10,
                       help="Maximum agent iterations (default: 10)")
    parser.add_argument("--debug", action="store_true",
                       help="Write debug log showing tool calls to debug_log.txt")
    args = parser.parse_args()

    debug = DebugLogger("debug_log.txt", model=MODEL) if args.debug else None

    # Setup working directory
    WORK_DIR = setup_work_directory(args.scripts)
    print(f"\nWorking directory: {WORK_DIR}\n")

    # Detect run script
    run_scripts = list(WORK_DIR.glob("run_*.py"))
    if not run_scripts:
        print("Error: No run_*.py script found")
        return
    run_script_name = run_scripts[0].name

    # Create LLM and agent with tools
    if "claude" in MODEL.lower():
        base_url = os.environ.get("ANTHROPIC_BASE_URL")
    else:
        base_url = os.environ.get("OPENAI_BASE_URL")


    llm = create_llm(MODEL, base_url=base_url)

    tools = [run_script, read_file, write_file, list_files]

    agent = create_agent(llm, tools)

    goal = AGENT_PROMPT.format(run_script_name=run_script_name)

    if debug:
        debug.log_prompt_and_tools(goal, tools)

    print("="*60)
    print("AGENT GOAL:")
    print(goal)
    print("="*60)
    print("\nStarting autonomous agent...")

    try:
        result = await agent.ainvoke({
            "messages": [("user", goal)]
        })

        if debug:
            debug.log_messages(result["messages"])

        print("\n" + "="*60)
        print("AGENT COMPLETED")
        print("="*60)
        print("\nFinal response:")
        content = result["messages"][-1].content
        if isinstance(content, list):
            content = "\n".join(block["text"] for block in content if block.get("type") == "text")
        print(content)

    except Exception as e:
        print(f"\nAgent error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

"""Tools for the ensemble agent — usable in-process or as a FastMCP server."""

import difflib
import glob
import os
import subprocess
import sys
from pathlib import Path

from ensemble_agent.archive import ArchiveManager

# Config — set via init() for in-process use, or env vars for MCP server mode
WORK_DIR = None
ARCHIVE = None
MAX_RUNS = 3
TIMEOUT = 300
run_count = 0
succeeded = False


def init(config, archive):
    """Initialize tools for in-process use."""
    global WORK_DIR, ARCHIVE, MAX_RUNS, TIMEOUT, run_count, succeeded
    WORK_DIR = archive.work_dir
    ARCHIVE = archive
    MAX_RUNS = config.max_runs
    TIMEOUT = config.script_timeout
    run_count = 0
    succeeded = False


def read_file(filepath: str) -> str:
    """Read a file to inspect its contents."""
    file_path = WORK_DIR / filepath
    if not file_path.exists():
        return f"ERROR: File '{filepath}' not found"
    return file_path.read_text()


def write_file(filepath: str, content: str) -> str:
    """Write/overwrite a file to fix scripts."""
    if ARCHIVE.run_succeeded:
        return "Script already ran successfully. No further changes needed."
    try:
        file_path = WORK_DIR / filepath
        old_lines = file_path.read_text().splitlines() if file_path.exists() else []
        new_lines = content.splitlines()
        changes = list(difflib.unified_diff(old_lines, new_lines, n=0))
        changed = [l for l in changes if l.startswith('+') and not l.startswith('+++')]

        file_path.write_text(content)
        ARCHIVE.start("fix")
        ARCHIVE.archive_scripts()

        if changed and len(changed) <= 3:
            summary = "; ".join(l[1:].strip() for l in changed)
            print(f"- Fixed: {filepath} ({summary})", file=sys.stderr, flush=True)
            return f"SUCCESS: Wrote {filepath} ({summary})"
        elif changed:
            print(f"- Fixed: {filepath} ({len(changed)} lines changed)", file=sys.stderr, flush=True)
            return f"SUCCESS: Wrote {filepath} ({len(changed)} lines changed)"
        print(f"- Saved: {filepath}", file=sys.stderr, flush=True)
        return f"SUCCESS: Wrote {filepath}"
    except Exception as e:
        return f"ERROR: {e}"


def list_files() -> str:
    """List Python files in working directory."""
    py_files = list(WORK_DIR.glob("*.py"))
    if not py_files:
        return "No Python files found"
    return "Files:\n" + "\n".join(f"- {f.name}" for f in py_files)


def run_script(script_name: str) -> str:
    """Run a Python script. Returns SUCCESS or FAILED with error details."""
    global run_count, succeeded

    if succeeded:
        return "Script already ran successfully. Do not run again."
    run_count += 1
    if run_count > MAX_RUNS:
        return "Run limit reached. Stop and report current status."

    script_path = WORK_DIR / script_name
    if not script_path.exists():
        return f"ERROR: Script '{script_name}' not found"

    print(f"Running {script_name}...", file=sys.stderr, flush=True)
    try:
        result = subprocess.run(
            ["python", script_name],
            cwd=WORK_DIR,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
        if result.returncode == 0:
            succeeded = True
            ARCHIVE.run_succeeded = True
            print("Script ran successfully", file=sys.stderr, flush=True)
            return f"SUCCESS\nOutput:\n{result.stdout[:500]}"
        else:
            error_msg = (
                f"Return code {result.returncode}\n"
                f"Stderr: {result.stderr}\n"
                f"Stdout: {result.stdout}"
            )
            print(f"Failed (code {result.returncode})", file=sys.stderr, flush=True)
            ARCHIVE.archive_run_output(error_msg)
            return (
                f"FAILED (code {result.returncode})\n"
                f"Stderr:\n{result.stderr}\n"
                f"Stdout:\n{result.stdout[:500]}"
            )
    except subprocess.TimeoutExpired:
        return f"ERROR: Script timed out ({TIMEOUT}s)"
    except Exception as e:
        return f"ERROR: {e}"


def generate_graphs() -> str:
    """Generate graphs from libEnsemble output files (.npy, .pickle).

    Produces objective progress plot and, if APOSMM was used,
    optimization runs plot. Call after a successful run.
    """
    from ensemble_agent.plotting import plot_objective, plot_local_runs

    graphs_dir = WORK_DIR / "graphs"
    graphs_dir.mkdir(parents=True, exist_ok=True)

    npy_files = glob.glob(str(WORK_DIR / "*.npy"))
    if not npy_files:
        return "No .npy output files found in work directory."

    latest_npy = max(npy_files, key=os.path.getmtime)
    run_name = os.path.splitext(os.path.basename(latest_npy))[0]

    generated = []
    summaries = []

    path, summary = plot_objective.plot(
        npy_file=latest_npy, run_name=run_name, output_dir=str(graphs_dir)
    )
    if path:
        generated.append(os.path.basename(path))
    summaries.append(summary)

    pickle_files = glob.glob(str(WORK_DIR / "*.pickle"))
    if pickle_files:
        latest_pickle = max(pickle_files, key=os.path.getmtime)
        try:
            path, summary = plot_local_runs.plot(
                npy_file=latest_npy, pickle_file=latest_pickle,
                run_name=run_name, output_dir=str(graphs_dir),
            )
            if path:
                generated.append(os.path.basename(path))
            summaries.append(summary)
        except Exception:
            pass

    return (
        f"Generated {len(generated)} graph(s) in graphs/:\n"
        f"  {', '.join(generated)}\n\n"
        + "\n".join(summaries)
    )


ALL_TOOLS = [read_file, write_file, list_files, run_script, generate_graphs]


def get_langchain_tools():
    """Return all tools wrapped as LangChain tools (for in-process use)."""
    from langchain_core.tools import tool
    return [tool(fn) for fn in ALL_TOOLS]


# --- MCP server mode (when run as standalone script) ---

if __name__ == "__main__":
    from fastmcp import FastMCP

    WORK_DIR = Path(os.environ.get("TOOL_WORK_DIR", "generated_scripts"))
    ARCHIVE = ArchiveManager(str(WORK_DIR))
    MAX_RUNS = int(os.environ.get("TOOL_MAX_RUNS", "3"))
    TIMEOUT = int(os.environ.get("TOOL_SCRIPT_TIMEOUT", "300"))

    mcp = FastMCP("ensemble-tools")
    for fn in ALL_TOOLS:
        mcp.tool()(fn)
    mcp.run(transport="stdio")

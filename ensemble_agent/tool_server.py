"""Tools for the ensemble agent — usable in-process or as a FastMCP server."""

import difflib
import glob
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import numpy as np

from ensemble_agent.archive import ArchiveManager

# Config — set via init() for in-process use, or env vars for MCP server mode
WORK_DIR = None
ARCHIVE = None
MAX_RUNS = 3
TIMEOUT = 300
run_count = 0
INTERACTIVE = False
ALLOW_INSTALL = False


def init(config, archive):
    """Initialize tools for in-process use."""
    global WORK_DIR, ARCHIVE, MAX_RUNS, TIMEOUT, run_count, INTERACTIVE, ALLOW_INSTALL
    WORK_DIR = archive.work_dir
    ARCHIVE = archive
    MAX_RUNS = config.max_runs
    TIMEOUT = config.script_timeout
    run_count = 0
    INTERACTIVE = config.interactive
    ALLOW_INSTALL = config.allow_install


def read_file(filepath: str) -> str:
    """Read a file. Accepts a filename in the working directory or an absolute path."""
    file_path = Path(filepath) if Path(filepath).is_absolute() else WORK_DIR / filepath
    if not file_path.exists():
        return f"ERROR: File '{filepath}' not found"
    return file_path.read_text()


def write_file(filepath: str, content: str) -> str:
    """Write/overwrite a file in the working directory."""
    try:
        if Path(filepath).is_absolute():
            return "ERROR: Cannot write to absolute paths. Use a filename to write in the working directory."
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
    global run_count

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
    try:
        from ensemble_agent.plotting import plot_objective, plot_local_runs
    except ImportError:
        return "Graphs skipped: matplotlib is not installed (pip install matplotlib)."

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


def install_package(package_name: str) -> str:
    """Install a Python package using pip."""
    if not INTERACTIVE and not ALLOW_INSTALL:
        return (
            f"Cannot install '{package_name}' in autonomous mode. "
            "Use --allow-install or run in interactive mode."
        )
    print(f"Installing {package_name}...", file=sys.stderr, flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print(f"Installed {package_name}", file=sys.stderr, flush=True)
            return f"SUCCESS: Installed {package_name}"
        else:
            print(f"Failed to install {package_name}", file=sys.stderr, flush=True)
            return f"FAILED: {result.stderr[:500]}"
    except subprocess.TimeoutExpired:
        return f"ERROR: Installation timed out for {package_name}"
    except Exception as e:
        return f"ERROR: {e}"


def check_results() -> str:
    """Check optimization results from the latest run output (.npy file)."""
    npy_files = glob.glob(str(WORK_DIR / "*.npy"))
    if not npy_files:
        return "No .npy output files found."
    latest = max(npy_files, key=os.path.getmtime)
    H = np.load(latest)
    fields = H.dtype.names
    summary = f"File: {os.path.basename(latest)}\n"
    summary += f"Fields: {fields}\n"
    summary += f"Total rows: {len(H)}\n"
    for name in fields:
        col = H[name]
        if col.dtype.kind in ('f', 'i'):
            summary += f"\n{name}: min={np.min(col):.6g}, max={np.max(col):.6g}, mean={np.mean(col):.6g}, unique={len(np.unique(col))}"
        elif col.dtype.kind == 'b':
            true_count = int(np.sum(col))
            if 0 < true_count < len(col):
                summary += f"\n{name}: {true_count}/{len(col)} True"
    return summary


def browse_directory(directory: str) -> str:
    """List contents of a subdirectory in the working area (e.g. 'ensemble/sim_0')."""
    target = WORK_DIR / directory
    if not target.exists():
        return f"Directory '{directory}' not found"
    if not target.is_dir():
        return f"'{directory}' is not a directory"
    entries = sorted(target.iterdir())
    if not entries:
        return "Empty directory"
    lines = []
    for e in entries:
        prefix = "[dir] " if e.is_dir() else "      "
        lines.append(f"{prefix}{e.name}")
    return "\n".join(lines)


REFERENCE_DOCS_DIR = Path(__file__).parent / "reference_docs"


def load_guide(topic: str) -> str:
    """Load a reference guide by topic name."""
    doc_path = REFERENCE_DOCS_DIR / f"{topic}.md"
    if not doc_path.exists():
        available = [f.stem for f in REFERENCE_DOCS_DIR.glob("*.md")]
        return f"Guide '{topic}' not found. Available: {available}"
    return doc_path.read_text()


EXAMPLES_INDEX_URL_TEMPLATE = (
    "https://raw.githubusercontent.com/Libensemble/libensemble"
    "/main/docs/{index_file}"
)


def get_examples(collection: str = "tests") -> str:
    """Get the index of available source files and their descriptions for a collection.

    Args:
        collection: Which collection to index. Options: tests, sim_funcs, vocs.
    """
    from .create_examples_index import COLLECTIONS, generate_index, write_markdown
    if collection not in COLLECTIONS:
        return f"Unknown collection '{collection}'. Available: {list(COLLECTIONS.keys())}"
    coll = COLLECTIONS[collection]
    index_path = REFERENCE_DOCS_DIR / coll["index_file"]
    if index_path.exists():
        return index_path.read_text()
    # Local collections generate from local directory
    if "local_path" in coll:
        entries = generate_index(
            directory=coll["local_path"],
            prefix=coll["prefix"],
            first_paragraph_only=True,
        )
        write_markdown(entries, str(index_path), title=coll["title"], description=coll["description"])
        return index_path.read_text()
    # Try URL
    try:
        url = EXAMPLES_INDEX_URL_TEMPLATE.format(index_file=coll["index_file"])
        with urllib.request.urlopen(url) as resp:
            content = resp.read().decode()
        index_path.write_text(content)
        return content
    except Exception:
        pass
    # Generate fresh from docstrings
    entries = generate_index(
        github_path=coll["github_path"],
        prefix=coll["prefix"],
        first_paragraph_only=True,
    )
    write_markdown(entries, str(index_path), title=coll["title"], description=coll["description"])
    return index_path.read_text()


def get_example(name: str, collection: str = "tests") -> str:
    """Fetch the full source code of a specific file by name (e.g. 'test_persistent_aposmm_nlopt').

    Args:
        name: The file name (with or without .py extension).
        collection: Which collection to fetch from. Options: tests, sim_funcs, vocs.
    """
    from .create_examples_index import COLLECTIONS, _raw_url
    if collection not in COLLECTIONS:
        return f"Unknown collection '{collection}'. Available: {list(COLLECTIONS.keys())}"
    coll = COLLECTIONS[collection]
    if not name.endswith(".py"):
        name = name + ".py"
    # Local collections read from disk
    if "local_path" in coll:
        filepath = Path(coll["local_path"]) / name
        if filepath.exists():
            return filepath.read_text()
        return f"ERROR: File '{name}' not found in {coll['local_path']}"
    url = f"{_raw_url(coll['github_path'])}/{name}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.read().decode()
    except Exception as e:
        return f"ERROR: Could not fetch {name}: {e}"


def run_python(code: str) -> str:
    """Execute a Python snippet and return its stdout. numpy is available as np. Runs in the working directory."""
    import io
    import contextlib
    buf = io.StringIO()
    prev_dir = os.getcwd()
    try:
        os.chdir(WORK_DIR)
        with contextlib.redirect_stdout(buf):
            exec(code, {"np": np, "__builtins__": __builtins__}, {})
    except Exception as e:
        return f"ERROR: {e}"
    finally:
        os.chdir(prev_dir)
    return buf.getvalue()


ALL_TOOLS = [
    read_file, write_file, list_files, run_script, generate_graphs,
    install_package, check_results, browse_directory, load_guide,
    get_examples, get_example, run_python,
]


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
    INTERACTIVE = os.environ.get("TOOL_INTERACTIVE", "").lower() in ("1", "true")
    ALLOW_INSTALL = os.environ.get("TOOL_ALLOW_INSTALL", "").lower() in ("1", "true")

    mcp = FastMCP("ensemble-tools")
    for fn in ALL_TOOLS:
        mcp.tool()(fn)
    mcp.run(transport="stdio")

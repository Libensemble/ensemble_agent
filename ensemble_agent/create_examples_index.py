#!/usr/bin/env python3
"""Generate index markdown files from libEnsemble source directories.

Fetches Python files from GitHub (default) or a local directory, extracts
module-level docstrings, and writes a markdown index file.

Supports multiple collections (tests, sim_funcs, etc.) via the COLLECTIONS config.
"""

import argparse
import ast
import json
import os
import sys
import urllib.request

# ---------------------------------------------------------------------------
# GitHub source configuration
# ---------------------------------------------------------------------------
GITHUB_REPO = "Libensemble/libensemble"
GITHUB_BRANCH = "main"

REFERENCE_DOCS_DIR = os.path.join(os.path.dirname(__file__), "reference_docs")

# Each collection defines a GitHub directory to index.
#   github_path: path within the repo
#   prefix:      only include files starting with this (empty string = all .py)
#   index_file:  output filename in reference_docs/
#   title:       markdown title for the index
#   description: second line of the markdown (used by load_guide discovery)
COLLECTIONS = {
    "tests": {
        "github_path": "libensemble/tests/regression_tests",
        "prefix": "test_",
        "index_file": "examples_index_libe.md",
        "title": "libEnsemble Examples Index",
        "description": "Reference index of libEnsemble regression test examples.",
    },
    "sim_funcs": {
        "github_path": "libensemble/sim_funcs",
        "prefix": "",
        "index_file": "sim_funcs_index_libe.md",
        "title": "libEnsemble Sim Functions Index",
        "description": "Reference index of libEnsemble simulation functions.",
    },
}


def _api_url(github_path):
    return (
        f"https://api.github.com/repos/{GITHUB_REPO}"
        f"/contents/{github_path}?ref={GITHUB_BRANCH}"
    )


def _raw_url(github_path):
    return (
        f"https://raw.githubusercontent.com/{GITHUB_REPO}"
        f"/{GITHUB_BRANCH}/{github_path}"
    )


# ---------------------------------------------------------------------------
# Docstring extraction
# ---------------------------------------------------------------------------

def extract_docstring(source, first_paragraph_only=False):
    """Extract module-level docstring from Python source code."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    docstring = ast.get_docstring(tree)
    if docstring and first_paragraph_only:
        paragraphs = docstring.split("\n\n")
        docstring = paragraphs[0].strip()
    return docstring


# ---------------------------------------------------------------------------
# File listing and fetching
# ---------------------------------------------------------------------------

def list_local_files(directory, prefix=""):
    """Return sorted list of .py filenames in a local directory."""
    return sorted(
        f for f in os.listdir(directory)
        if f.endswith(".py") and f.startswith(prefix)
    )


def read_local_file(directory, filename):
    """Read a local file and return its contents."""
    path = os.path.join(directory, filename)
    with open(path) as f:
        return f.read()


def list_remote_files(github_path, prefix=""):
    """Return sorted list of .py filenames from GitHub API."""
    req = urllib.request.Request(_api_url(github_path))
    req.add_header("Accept", "application/vnd.github.v3+json")
    with urllib.request.urlopen(req) as resp:
        entries = json.loads(resp.read().decode())

    return sorted(
        e["name"] for e in entries
        if e["name"].endswith(".py") and e["name"].startswith(prefix)
    )


def fetch_remote_file(github_path, filename):
    """Fetch a single file from GitHub raw content."""
    url = f"{_raw_url(github_path)}/{filename}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------

def generate_index(github_path=None, prefix="", directory=None,
                   first_paragraph_only=False):
    """Generate list of (name, docstring) tuples.

    Args:
        github_path: GitHub repo path to fetch from (used when directory is None).
        prefix: Only include files starting with this prefix.
        directory: Local directory to read from instead of GitHub.
        first_paragraph_only: Truncate docstrings to first paragraph.
    """
    if github_path is None and directory is None:
        github_path = COLLECTIONS["tests"]["github_path"]
        prefix = prefix or COLLECTIONS["tests"]["prefix"]

    if directory:
        filenames = list_local_files(directory, prefix)
        read_fn = lambda f: read_local_file(directory, f)
        source_label = directory
    else:
        filenames = list_remote_files(github_path, prefix)
        read_fn = lambda f: fetch_remote_file(github_path, f)
        source_label = f"{GITHUB_REPO}/{github_path} ({GITHUB_BRANCH})"

    print(f"Source: {source_label}")
    print(f"Found {len(filenames)} files")

    entries = []
    for i, filename in enumerate(filenames, 1):
        name = filename.removesuffix(".py")
        print(f"  [{i}/{len(filenames)}] {name}")
        try:
            source = read_fn(filename)
            docstring = extract_docstring(source, first_paragraph_only)
        except Exception as e:
            print(f"    WARNING: {e}")
            docstring = None

        entries.append((name, docstring))

    return entries


def write_markdown(entries, output_path, title=None, description=None):
    """Write the index markdown file."""
    title = title or "Index"
    description = description or ""

    lines = [f"# {title}", "", description, ""]

    for name, docstring in entries:
        lines.append(f"## {name}")
        lines.append("")
        if docstring:
            lines.append(docstring)
        else:
            lines.append("*No description available.*")
        lines.append("")

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote {len(entries)} entries to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate index from a libEnsemble source directory."
    )
    parser.add_argument(
        "collection",
        nargs="?",
        default="tests",
        choices=list(COLLECTIONS.keys()),
        help=f"Which collection to index (default: tests). Options: {list(COLLECTIONS.keys())}",
    )
    parser.add_argument(
        "--local-dir",
        help="Read files from this local directory instead of GitHub.",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output markdown file (default: auto from collection config).",
    )
    parser.add_argument(
        "--first-paragraph",
        action="store_true",
        help="Use only the first paragraph of each docstring.",
    )
    args = parser.parse_args()

    coll = COLLECTIONS[args.collection]
    output = args.output or os.path.join(REFERENCE_DOCS_DIR, coll["index_file"])

    entries = generate_index(
        github_path=coll["github_path"],
        prefix=coll["prefix"],
        directory=args.local_dir,
        first_paragraph_only=args.first_paragraph,
    )
    write_markdown(entries, output, title=coll["title"], description=coll["description"])


if __name__ == "__main__":
    main()

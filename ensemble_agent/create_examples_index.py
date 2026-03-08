#!/usr/bin/env python3
"""Generate an examples index markdown file from libEnsemble regression tests.

Fetches test files from GitHub (default) or a local directory, extracts
module-level docstrings, and writes a markdown index file.
"""

import argparse
import ast
import json
import os
import sys
import urllib.request

# ---------------------------------------------------------------------------
# Default source: libEnsemble regression tests on GitHub
# ---------------------------------------------------------------------------
GITHUB_REPO = "Libensemble/libensemble"
GITHUB_BRANCH = "main"
GITHUB_TESTS_PATH = "libensemble/tests/regression_tests"

GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO}"
    f"/contents/{GITHUB_TESTS_PATH}?ref={GITHUB_BRANCH}"
)
GITHUB_RAW_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_REPO}"
    f"/{GITHUB_BRANCH}/{GITHUB_TESTS_PATH}"
)

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(__file__), "reference_docs", "examples_index_libe.md"
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

def list_local_files(directory):
    """Return sorted list of .py filenames in a local directory."""
    return sorted(
        f for f in os.listdir(directory)
        if f.endswith(".py") and f.startswith("test_")
    )


def read_local_file(directory, filename):
    """Read a local file and return its contents."""
    path = os.path.join(directory, filename)
    with open(path) as f:
        return f.read()


def list_remote_files():
    """Return sorted list of .py filenames from GitHub API."""
    req = urllib.request.Request(GITHUB_API_URL)
    req.add_header("Accept", "application/vnd.github.v3+json")
    with urllib.request.urlopen(req) as resp:
        entries = json.loads(resp.read().decode())

    return sorted(
        e["name"] for e in entries
        if e["name"].endswith(".py") and e["name"].startswith("test_")
    )


def fetch_remote_file(filename):
    """Fetch a single file from GitHub raw content."""
    url = f"{GITHUB_RAW_URL}/{filename}"
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------

def generate_index(directory=None, first_paragraph_only=False):
    """Generate list of (test_name, docstring) tuples."""
    if directory:
        filenames = list_local_files(directory)
        read_fn = lambda f: read_local_file(directory, f)
        source_label = directory
    else:
        filenames = list_remote_files()
        read_fn = fetch_remote_file
        source_label = f"{GITHUB_REPO} ({GITHUB_BRANCH})"

    print(f"Source: {source_label}")
    print(f"Found {len(filenames)} test files")

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


def write_markdown(entries, output_path):
    """Write the index markdown file."""
    lines = [
        "# libEnsemble Examples Index",
        "",
        "Reference index of libEnsemble regression test examples.",
        "",
    ]

    for name, docstring in entries:
        lines.append(f"## {name}")
        lines.append("")
        if docstring:
            lines.append(docstring)
        else:
            lines.append("*No description available.*")
        lines.append("")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nWrote {len(entries)} entries to {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate examples index from libEnsemble regression tests."
    )
    parser.add_argument(
        "--local-dir",
        help="Read test files from this local directory instead of GitHub.",
    )
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT,
        help=f"Output markdown file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--first-paragraph",
        action="store_true",
        help="Use only the first paragraph of each docstring.",
    )
    args = parser.parse_args()

    entries = generate_index(
        directory=args.local_dir,
        first_paragraph_only=args.first_paragraph,
    )
    write_markdown(entries, args.output)


if __name__ == "__main__":
    main()

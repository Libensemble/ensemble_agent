"""Script parsing, saving, and detection utilities."""

import re
import shutil
from pathlib import Path


def parse_scripts(text):
    """Parse '=== filename ===' delimited text into {filename: content} dict."""
    pattern = r"=== (.+?) ===\n(.*?)(?=\n===|$)"
    matches = re.findall(pattern, text, re.DOTALL)
    return {filename.strip(): content.strip() + "\n" for filename, content in matches}


def save_scripts(scripts_text, output_dir, archive_name=None):
    """Save scripts from '=== filename ===' format to files, optionally archiving."""
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    parsed = parse_scripts(scripts_text)
    for filename, content in parsed.items():
        filepath = output_dir / filename
        filepath.write_text(content)
        print(f"- Saved: {filepath}")

    if archive_name:
        archive_dir = output_dir / "versions" / archive_name
        archive_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in parsed.items():
            (archive_dir / filename).write_text(content)


def detect_run_script(directory):
    """Find the run script in directory (first run_*.py file)."""
    directory = Path(directory)
    run_scripts = list(directory.glob("run_*.py"))
    return run_scripts[0].name if run_scripts else None


def copy_existing_scripts(scripts_dir, output_dir):
    """Copy scripts from existing directory and return as formatted text."""
    scripts_dir = Path(scripts_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    scripts_text = ""
    for script_file in sorted(scripts_dir.glob("*.py")):
        shutil.copy(script_file, output_dir)
        print(f"Copied: {script_file.name}")
        scripts_text += f"=== {script_file.name} ===\n{script_file.read_text()}\n\n"
    return scripts_text


def clean_llm_output(text):
    """Strip markdown code fences and extract === delimited scripts."""
    text = re.sub(r"```python\n", "", text)
    text = re.sub(r"```\n?", "", text)
    if "===" in text:
        start = text.find("===")
        text = text[start:]
    return text

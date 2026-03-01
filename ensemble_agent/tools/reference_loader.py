"""Reference doc loader — loads markdown reference docs into the system prompt."""

from pathlib import Path

from .base import ToolProvider

REFERENCE_DOCS_DIR = Path(__file__).parent.parent / "reference_docs"


class ReferenceLoader(ToolProvider):
    """Loads markdown reference docs and injects them into the system prompt."""

    def get_tools(self):
        return []

    def get_prompt_fragment(self):
        if not REFERENCE_DOCS_DIR.exists():
            return ""
        parts = []
        for f in sorted(REFERENCE_DOCS_DIR.glob("*.md")):
            parts.append(f.read_text().strip())
        if not parts:
            return ""
        return "Reference information:\n\n" + "\n\n---\n\n".join(parts)

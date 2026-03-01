"""File operations — read, write, list files in the work directory."""

import difflib
from pathlib import Path

from pydantic import BaseModel, Field
from langchain_core.tools import StructuredTool

from .base import ToolProvider


class ReadFileInput(BaseModel):
    filepath: str = Field(description="Path to file relative to work directory")


class WriteFileInput(BaseModel):
    filepath: str = Field(description="Path to file relative to work directory")
    content: str = Field(description="Full content to write")


class ListFilesInput(BaseModel):
    pass


class FileOpsTools(ToolProvider):
    """Provides read_file, write_file, and list_files tools."""

    def get_tools(self):
        work_dir = self.archive.work_dir
        archive = self.archive

        async def read_file_tool(filepath: str) -> str:
            file_path = work_dir / filepath
            if not file_path.exists():
                return f"ERROR: File '{filepath}' not found"
            return file_path.read_text()

        async def write_file_tool(filepath: str, content: str) -> str:
            if archive.run_succeeded:
                return "Script already ran successfully. No further changes needed."
            try:
                file_path = work_dir / filepath
                # Diff against old content for summary
                old_lines = file_path.read_text().splitlines() if file_path.exists() else []
                new_lines = content.splitlines()
                changes = list(difflib.unified_diff(old_lines, new_lines, n=0))
                changed = [l for l in changes if l.startswith('+') and not l.startswith('+++')]

                file_path.write_text(content)
                archive.start("fix")
                archive.archive_scripts()

                if changed and len(changed) <= 3:
                    summary = "; ".join(l[1:].strip() for l in changed)
                    print(f"- Fixed: {filepath} ({summary})", flush=True)
                elif changed:
                    print(f"- Fixed: {filepath} ({len(changed)} lines changed)", flush=True)
                else:
                    print(f"- Saved: {filepath}", flush=True)
                return f"SUCCESS: Wrote {filepath}"
            except Exception as e:
                return f"ERROR: {e}"

        async def list_files_tool() -> str:
            py_files = list(work_dir.glob("*.py"))
            if not py_files:
                return "No Python files found"
            return "Files:\n" + "\n".join(f"- {f.name}" for f in py_files)

        return [
            StructuredTool(
                name="read_file",
                description="Read a file to inspect its contents.",
                args_schema=ReadFileInput,
                coroutine=read_file_tool,
            ),
            StructuredTool(
                name="write_file",
                description="Write/overwrite a file to fix scripts.",
                args_schema=WriteFileInput,
                coroutine=write_file_tool,
            ),
            StructuredTool(
                name="list_files",
                description="List Python files in working directory.",
                args_schema=ListFilesInput,
                coroutine=list_files_tool,
            ),
        ]

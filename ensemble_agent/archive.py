"""Versioned script and output archiving — no global state."""

import shutil
import time
from pathlib import Path

from .config import ARCHIVE_ITEMS, ARCHIVE_RUNS_DIR


class ArchiveManager:
    """Tracks versioned archives of scripts and run outputs."""

    def __init__(self, work_dir):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 1
        self._current = None

    @property
    def current_archive(self):
        return self._current

    def start(self, action):
        """Begin a new versioned archive (e.g. '1_generated', '2_fix')."""
        self._current = f"{self._counter}_{action}"
        (self.work_dir / "versions" / self._current).mkdir(parents=True, exist_ok=True)
        self._counter += 1

    def archive_scripts(self):
        """Copy current *.py files into the active version directory."""
        if not self._current:
            return
        dest = self.work_dir / "versions" / self._current
        for f in self.work_dir.glob("*.py"):
            shutil.copy(f, dest / f.name)

    def archive_run_output(self, error_msg=""):
        """Move run artifacts into the active version's output/ subdirectory."""
        if not self._current:
            return
        output_dir = self.work_dir / "versions" / self._current / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        if error_msg:
            (output_dir / "error.txt").write_text(error_msg)

        for item in ARCHIVE_ITEMS:
            item_path = self.work_dir / item
            if item_path.exists() and item_path.is_dir():
                shutil.copytree(str(item_path), str(output_dir / item), dirs_exist_ok=True)
                shutil.rmtree(str(item_path))
            else:
                for fp in self.work_dir.glob(item):
                    if fp.is_file():
                        shutil.copy(str(fp), str(output_dir / fp.name))
                        fp.unlink()

    @staticmethod
    def archive_existing_output_dir(output_dir, archive_parent=None):
        """If output_dir exists, move it to archive_parent/output_dir_<unique>, then create fresh."""
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

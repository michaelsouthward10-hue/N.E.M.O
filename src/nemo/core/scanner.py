import os
from pathlib import Path

from nemo.core.paths import DATA_DIR
from nemo.indexing.indexer import VaultIndexer
from nemo.indexing.parser import MarkdownParser


EXCLUDED_DIRECTORIES = {
    ".git",
    ".hg",
    ".obsidian",
    ".svn",
    ".trash",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "env",
    "node_modules",
    "venv",
}


class VaultScanner:
    def __init__(self, vault_path, ai=None):
        self.vault = Path(vault_path)
        self.indexer = VaultIndexer(self.vault)
        # Kept for callers that construct the scanner with an AI client. Reindexing
        # only parses local Markdown; it no longer waits on a model for every note.
        self.ai = ai

    @staticmethod
    def _summary(text):
        for line in text.splitlines():
            content = line.strip()
            if not content or content in {"---", "```"} or content.startswith("#"):
                continue
            return content[:500]
        return ""

    def scan(self, progress_callback=None):
        def report(message):
            if progress_callback:
                progress_callback(message)

        report("Finding Markdown notes…")
        folders = 0
        other = 0
        walk_errors = []
        markdown_files = []
        next_folder_update = 100

        for current, directories, filenames in os.walk(
            self.vault,
            onerror=walk_errors.append,
        ):
            directories[:] = sorted(
                name for name in directories
                if name.casefold() not in EXCLUDED_DIRECTORIES
            )
            folders += len(directories)

            for filename in filenames:
                path = Path(current, filename)
                if path.suffix.casefold() == ".md":
                    markdown_files.append(path)
                else:
                    other += 1

            if folders >= next_folder_update:
                report(f"Searching vault… {folders} folders checked")
                next_folder_update = folders + 100

        total = len(markdown_files)
        report(f"Indexing 0 of {total} Markdown notes…")
        unreadable = len(walk_errors)

        for number, path in enumerate(markdown_files, start=1):
            try:
                note = MarkdownParser(path).parse()
            except OSError:
                unreadable += 1
                continue

            note["summary"] = self._summary(note["text"])
            self.indexer.add_note(note)

            if number % 10 == 0 or number == total:
                report(f"Indexing {number} of {total} Markdown notes…")

        self.indexer.save(DATA_DIR / "index.json")
        return {
            "folders": folders,
            "markdown": len(self.indexer.index),
            "other": other,
            "unreadable": unreadable,
        }

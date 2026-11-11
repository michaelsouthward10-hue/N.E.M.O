import os
from pathlib import Path

from nemo.core.paths import DATA_DIR
from nemo.core.storage import index_path, load_vault_index
from nemo.indexing.indexer import VaultIndexer
from nemo.indexing.parser import MarkdownParser

EXCLUDED_DIRECTORIES = {".git", ".hg", ".obsidian", ".svn", ".trash", ".venv",
                        "__pycache__", "build", "dist", "env", "node_modules", "venv", ".nemo-build", ".nemo-release"}


class ScanCancelled(Exception):
    pass


class VaultScanner:
    def __init__(self, vault_path, ai=None):
        self.vault = Path(vault_path).resolve()
        self.indexer = VaultIndexer(self.vault)
        self.ai = ai

    @staticmethod
    def _summary(text):
        for line in text.splitlines():
            content = line.strip()
            if content and content not in {"---", "```"} and not content.startswith("#"):
                return content[:500]
        return ""

    def scan(self, progress_callback=None, metrics_callback=None, incremental=False, cancel_event=None):
        def check_cancelled():
            if cancel_event and cancel_event.is_set():
                raise ScanCancelled("Indexing stopped. The previous index has been kept.")

        def report(message, phase="discovering", completed=0, total=0):
            if progress_callback:
                progress_callback(message)
            if metrics_callback:
                metrics_callback({"message": message, "phase": phase, "completed": completed, "total": total})

        if not self.vault.is_dir():
            raise FileNotFoundError("The selected vault is unavailable. Its previous index has been kept.")
        destination = index_path(self.vault, DATA_DIR)
        try:
            previous = load_vault_index(destination, self.vault)
        except (ValueError, OSError):
            if incremental:
                raise ValueError("The saved index could not be read. Click Reindex to rebuild it.")
            previous = {}
        self.indexer.index = {}
        report("Finding Markdown notes...")
        other = folders = 0
        walk_errors = []
        files = []
        for current, directories, filenames in os.walk(self.vault, onerror=walk_errors.append):
            check_cancelled()
            directories[:] = sorted(name for name in directories
                                    if name.casefold() not in EXCLUDED_DIRECTORIES
                                    and not Path(current, name).is_symlink())
            folders += 1
            for filename in sorted(filenames):
                path = Path(current, filename)
                if path.is_symlink():
                    continue
                if path.suffix.casefold() == ".md":
                    files.append(path)
                else:
                    other += 1
            if folders % 100 == 0:
                report(f"Searching vault... {folders} folders checked")
        total = len(files)
        unreadable = len(walk_errors)
        changed = reused = 0
        seen = set()
        report(f"Scanned 0 of {total} Markdown notes...", "indexing", 0, total)
        for number, path in enumerate(files, 1):
            check_cancelled()
            relative = path.relative_to(self.vault).as_posix()
            seen.add(relative)
            old = previous.get(relative)
            try:
                stat = path.stat()
                signature = [stat.st_mtime_ns, stat.st_size]
                if incremental and old and old.get("signature") == signature:
                    note = old
                    reused += 1
                else:
                    note = MarkdownParser(path).parse()
                    note.update(path=relative, summary=self._summary(note["text"]), signature=signature)
                    changed += 1
                self.indexer.add_note(note)
            except OSError:
                unreadable += 1
                if old:
                    self.indexer.add_note(old)
            if number % 10 == 0 or number == total:
                report(f"Scanned {number} of {total} Markdown notes...", "indexing", number, total)
        # A failed directory walk is not evidence that its notes were deleted.
        if walk_errors:
            for key, note in previous.items():
                if key not in seen:
                    self.indexer.add_note(note)
        removed = len(set(previous) - set(self.indexer.index))
        check_cancelled()
        report("Saving the note index...", "saving", total, total)
        if changed or removed or not destination.exists() or not incremental:
            self.indexer.save(destination)
        return {"scanned": total, "folders": folders, "markdown": len(self.indexer.index),
                "other": other, "unreadable": unreadable, "changed": changed,
                "reused": reused, "removed": removed}

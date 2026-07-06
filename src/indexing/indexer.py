import json
from pathlib import Path


class VaultIndexer:

    def __init__(self, vault):
        self.vault = vault
        self.index = {}

    def add_note(self, note):
        """Add a parsed note to the index."""
        self.index[note["title"]] = note

    def save(self, destination):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with open(destination, "w", encoding="utf-8") as f:
            json.dump(
                self.index,
                f,
                indent=4,
                ensure_ascii=False
            )
from pathlib import Path

from nemo.core.storage import atomic_json_write, vault_identity


class VaultIndexer:
    def __init__(self, vault):
        self.vault = Path(vault)
        self.index = {}

    def add_note(self, note):
        self.index[note.get("path", note["title"])] = note

    def save(self, destination):
        atomic_json_write(destination, {
            "schema": 2, "vault": vault_identity(self.vault), "notes": self.index,
        })

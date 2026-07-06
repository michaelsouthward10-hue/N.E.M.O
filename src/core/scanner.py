from pathlib import Path
from indexing.indexer import VaultIndexer
from indexing.parser import MarkdownParser

class VaultScanner:

    def __init__(self, vault_path):
        self.vault = Path(vault_path)
        self.indexer = VaultIndexer(self.vault)

    def scan(self):

        folders = 0
        markdown = 0
        other = 0

        for item in self.vault.rglob("*"):
            if item.is_dir():
                folders += 1
            elif item.suffix.lower() == ".md":
                markdown += 1
                parser = MarkdownParser(item)
                note = parser.parse()
                self.indexer.add_note(note)
            else:
                other += 1

        self.indexer.save("data/index.json")

        return {
            "folders": folders,
            "markdown": markdown,
            "other": other,
        }
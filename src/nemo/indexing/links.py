"""Resolve Obsidian links without merging notes that share a filename."""
from collections import Counter
import posixpath


def note_id(key, note):
    return note.get("path", key)


class LinkResolver:
    def __init__(self, index):
        self.index = index
        self.paths = {str(note_id(key, note)).casefold().removesuffix(".md"): key for key, note in index.items()}
        self.names = {}
        for key, note in index.items():
            for name in [note.get("title", key), *note.get("aliases", [])]:
                self.names.setdefault(str(name).casefold(), set()).add(key)

    def resolve(self, link, source=""):
        target = str(link).split("|", 1)[0].split("#", 1)[0].strip().replace("\\", "/").casefold().removesuffix(".md")
        if not target:
            return source if source in self.index else None
        if target in self.paths:
            return self.paths[target]
        relative = posixpath.normpath(posixpath.join(posixpath.dirname(source).casefold(), target))
        if relative in self.paths:
            return self.paths[relative]
        matches = self.names.get(target, set())
        return next(iter(matches)) if len(matches) == 1 else None


def resolve_link(link, source, index):
    return LinkResolver(index).resolve(link, source)


def display_names(index):
    counts = Counter(note.get("title", key).casefold() for key, note in index.items())
    return {key: (note.get("title", key) if counts[note.get("title", key).casefold()] == 1
                  else note.get("path", key)) for key, note in index.items()}

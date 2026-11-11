import json
import os
import threading

import pytest

from nemo.core import scanner as scanner_module
from nemo.core.scanner import ScanCancelled, VaultScanner
from nemo.core.storage import index_path, load_vault_index
from nemo.graph.knowledge_graph import KnowledgeGraph
from nemo.search.search_engine import SearchEngine


def write_note(vault, path, text):
    file = vault / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    return file


def test_vaults_and_duplicate_filenames_never_share_notes(tmp_path, isolated_data):
    first, second = tmp_path / "first", tmp_path / "second"
    write_note(first, "Past/Michael.md", "An old account of Michael.")
    write_note(first, "Present/Michael.md", "A different account of Michael.")
    write_note(second, "Lucifer.md", "Only in the second vault.")
    VaultScanner(first).scan()
    VaultScanner(second).scan()
    search = SearchEngine(first)
    assert set(search.index) == {"Past/Michael.md", "Present/Michael.md"}
    assert search.search_by_title("Michael") is None
    assert search.search_by_title("Past/Michael")["text"] == "An old account of Michael."
    assert set(SearchEngine(second).index) == {"Lucifer.md"}
    assert index_path(first, isolated_data) != index_path(second, isolated_data)


def test_incremental_updates_changes_moves_and_deletions(tmp_path):
    vault = tmp_path / "vault"
    unchanged = write_note(vault, "Unchanged.md", "Keep this.")
    changed = write_note(vault, "Changed.md", "First.")
    moved = write_note(vault, "Old.md", "A moving note.")
    removed = write_note(vault, "Removed.md", "Remove me.")
    VaultScanner(vault).scan()
    original = scanner_module.MarkdownParser.parse
    parsed = []
    def parse(parser):
        parsed.append(parser.file.name)
        return original(parser)
    changed.write_text("The new, longer content.")
    moved.rename(vault / "New.md")
    removed.unlink()
    from unittest.mock import patch
    with patch.object(scanner_module.MarkdownParser, "parse", parse):
        result = VaultScanner(vault).scan(incremental=True)
    assert parsed == ["Changed.md", "New.md"]
    assert result["changed"] == 2 and result["reused"] == 1 and result["removed"] == 2
    assert SearchEngine(vault).index["Changed.md"]["text"] == "The new, longer content."


def test_atomic_save_failure_keeps_previous_index(tmp_path, isolated_data, monkeypatch):
    vault = tmp_path / "vault"
    file = write_note(vault, "Note.md", "Original.")
    VaultScanner(vault).scan()
    destination = index_path(vault, isolated_data)
    before = destination.read_bytes()
    file.write_text("New contents.")
    from nemo.core import storage
    def fail(*args):
        raise OSError("Disk full")
    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError, match="Disk full"):
        VaultScanner(vault).scan()
    assert destination.read_bytes() == before
    assert not list(destination.parent.glob(".nemo-*.tmp"))


def test_cancel_never_replaces_previous_index(tmp_path, isolated_data):
    vault = tmp_path / "vault"
    write_note(vault, "Note.md", "Original.")
    VaultScanner(vault).scan()
    destination = index_path(vault, isolated_data)
    before = destination.read_bytes()
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ScanCancelled):
        VaultScanner(vault).scan(cancel_event=cancel)
    assert destination.read_bytes() == before


def test_unreadable_existing_note_is_preserved_for_retry(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    write_note(vault, "Note.md", "Keep the last readable content.")
    VaultScanner(vault).scan()
    def fail(parser):
        raise OSError("Access denied")
    monkeypatch.setattr(scanner_module.MarkdownParser, "parse", fail)
    result = VaultScanner(vault).scan()
    assert result["unreadable"] == 1
    assert SearchEngine(vault).index["Note.md"]["text"] == "Keep the last readable content."


def test_unreadable_folder_does_not_erase_its_notes(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    write_note(vault, "Hidden/Note.md", "Do not erase this.")
    VaultScanner(vault).scan()
    def incomplete_walk(root, onerror=None):
        onerror(PermissionError("Access denied"))
        yield str(root), [], []
    monkeypatch.setattr(scanner_module.os, "walk", incomplete_walk)
    result = VaultScanner(vault).scan(incremental=True)
    assert result["removed"] == 0
    assert "Hidden/Note.md" in SearchEngine(vault).index


def test_graph_resolves_qualified_links_without_merging_duplicates(tmp_path):
    vault = tmp_path / "vault"
    write_note(vault, "Past/Michael.md", "[[Past/Lucifer]]")
    write_note(vault, "Present/Michael.md", "[[Present/Lucifer]]")
    write_note(vault, "Past/Lucifer.md", "Old")
    write_note(vault, "Present/Lucifer.md", "New")
    VaultScanner(vault).scan()
    graph = KnowledgeGraph()
    graph.build(SearchEngine(vault).index)
    assert graph.find_path("Past/Michael.md", "Past/Lucifer.md")
    assert graph.find_path("Past/Michael.md", "Present/Lucifer.md") is None


def test_corrupted_or_wrong_vault_index_is_not_served(tmp_path, isolated_data):
    vault = tmp_path / "vault"
    write_note(vault, "Note.md", "Content")
    VaultScanner(vault).scan()
    destination = index_path(vault, isolated_data)
    value = json.loads(destination.read_text(encoding="utf-8"))
    value["vault"] = "another vault"
    destination.write_text(json.dumps(value), encoding="utf-8")
    engine = SearchEngine(vault)
    assert not engine.index and engine.warning
    with pytest.raises(ValueError):
        VaultScanner(vault).scan(incremental=True)
    VaultScanner(vault).scan()
    assert SearchEngine(vault).index

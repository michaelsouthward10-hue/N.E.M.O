from nemo.core import scanner as scanner_module
from nemo.core.scanner import VaultScanner
from nemo.gui import NemoDesktopApp
from nemo.core.storage import index_path
from types import SimpleNamespace
import tkinter as tk
from conftest import clear_tk


def test_progress_reports_total_and_counts_inaccessible_notes(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "readable.md").write_text("# Readable")
    (vault / "blocked.md").write_text("# Blocked")
    excluded = vault / ".obsidian"
    excluded.mkdir()
    (excluded / "ignored.md").write_text("Ignored")
    monkeypatch.setattr(scanner_module, "DATA_DIR", tmp_path / "data")
    parse = scanner_module.MarkdownParser.parse
    def parse_note(parser):
        if parser.file.name == "blocked.md":
            raise OSError("Access denied")
        return parse(parser)
    monkeypatch.setattr(scanner_module.MarkdownParser, "parse", parse_note)
    events = []
    result = VaultScanner(vault).scan(metrics_callback=events.append)
    assert result["scanned"] == 2
    assert result["markdown"] == 1
    assert result["unreadable"] == 1
    assert events[0]["phase"] == "discovering"
    indexing = [event for event in events if event["phase"] == "indexing"]
    assert indexing[0]["completed"] == 0
    assert indexing[-1]["completed"] == indexing[-1]["total"] == 2
    assert events[-1]["phase"] == "saving"
    assert index_path(vault, tmp_path / "data").is_file()


def test_empty_vault_finishes_with_zero_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner_module, "DATA_DIR", tmp_path / "data")
    vault = tmp_path / "empty"
    vault.mkdir()
    events = []
    result = VaultScanner(vault).scan(metrics_callback=events.append)
    assert result["scanned"] == result["markdown"] == 0
    assert events[-1]["phase"] == "saving"


def test_saving_failure_propagates_instead_of_reporting_success(tmp_path, monkeypatch):
    def fail_save(*args):
        raise OSError("Disk full")
    monkeypatch.setattr(scanner_module.VaultIndexer, "save", fail_save)
    import pytest
    with pytest.raises(OSError, match="Disk full"):
        VaultScanner(tmp_path).scan()


def test_desktop_progress_lifecycle(monkeypatch, tmp_path, tk_root):
    from nemo import gui
    monkeypatch.setattr(gui, "load_settings", lambda: {"vault": {"path": str(tmp_path)}, "ai": {"endpoint": "http://localhost:11434", "model": "test"}})
    monkeypatch.setattr(gui.NemoDesktopApp, "_check_ollama", lambda self: None)
    root = tk_root
    try:
        app = NemoDesktopApp(root)
        app._begin_reindex()
        assert str(app.reindex_progress["mode"]) == "indeterminate"
        app._update_reindex_progress({"message": "Scanned 10 of 20 Markdown notes…", "phase": "indexing", "completed": 10, "total": 20})
        assert float(app.reindex_progress["value"]) == 10
        assert float(app.reindex_progress["maximum"]) == 20
        app._start_update_check = lambda manual: None
        app.results.put(("reindex", {"scanned": 20, "markdown": 19, "unreadable": 1}, None))
        app._poll_results()
        assert app.reindex_heading.get() == "Reindex complete"
        assert "20 Markdown notes" in app.reindex_detail.get()
        assert "Skipped 1" in app.reindex_detail.get()
        app._begin_reindex()
        app.results.put(("reindex", None, OSError("Disk full")))
        app._poll_results()
        assert app.reindex_heading.get() == "Reindex failed"
        assert app.reindex_detail.get() == "Disk full"
        app._begin_reindex()
        app._finish_reindex({"scanned": 0, "markdown": 0})
        assert "0 Markdown notes" in app.reindex_detail.get()
    finally:
        app._closed = True
        app.cancel_event.set()
        clear_tk(root)

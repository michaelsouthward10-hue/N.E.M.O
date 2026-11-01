import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from nemo import gui
from nemo.core import scanner as scanner_module
from nemo.core.scanner import VaultScanner


def make_app(vault, indexed_notes):
    app = gui.NemoDesktopApp.__new__(gui.NemoDesktopApp)
    app.settings = {"vault": {"path": str(vault)}}
    app.chat = SimpleNamespace(
        search=SimpleNamespace(search_by_title=lambda title: indexed_notes.get(title))
    )
    return app


def test_reindex_stores_vault_relative_note_paths(tmp_path, monkeypatch):
    vault = tmp_path / "My Vault"
    note = vault / "Characters" / "Michael.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Michael\nAn archangel.", encoding="utf-8")
    monkeypatch.setattr(scanner_module, "DATA_DIR", tmp_path / "local-data")

    VaultScanner(vault).scan()

    index = json.loads((tmp_path / "local-data" / "index.json").read_text(encoding="utf-8"))
    assert index["Michael"]["path"] == "Characters/Michael.md"


def test_source_resolves_to_the_indexed_markdown_file(tmp_path):
    vault = tmp_path / "My Vault"
    note = vault / "Characters" / "Michael.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Michael", encoding="utf-8")
    app = make_app(vault, {"Michael": {"title": "Michael", "path": "Characters/Michael.md"}})

    assert app._resolve_source_path("Michael") == note.resolve()


def test_source_opens_the_note_with_an_obsidian_uri(tmp_path, monkeypatch):
    vault = tmp_path / "My Vault"
    note = vault / "Characters" / "Michael Southward.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Michael", encoding="utf-8")
    app = make_app(
        vault,
        {"Michael Southward": {"title": "Michael Southward", "path": "Characters/Michael Southward.md"}},
    )
    opened = []
    monkeypatch.setattr(gui.webbrowser, "open", lambda uri: opened.append(uri) or True)

    app._open_source("Michael Southward")

    assert len(opened) == 1
    parsed = urlparse(opened[0])
    assert parsed.scheme == "obsidian"
    assert parsed.netloc == "open"
    assert parse_qs(parsed.query)["path"] == [str(note.resolve())]


def test_source_resolves_legacy_index_by_note_title(tmp_path):
    vault = tmp_path / "My Vault"
    note = vault / "Characters" / "Michael.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Michael", encoding="utf-8")
    app = make_app(vault, {"Michael": {"title": "Michael"}})

    assert app._resolve_source_path("Michael") == note.resolve()

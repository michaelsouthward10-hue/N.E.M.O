"""Tests never read or write the user's vault index or saved conversations."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(scope="session")
def tk_root():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


def clear_tk(root):
    for identity in root.tk.call("after", "info"):
        root.after_cancel(identity)
    for child in root.winfo_children():
        child.destroy()


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    from nemo.core import paths, scanner
    from nemo.search import search_engine
    data = tmp_path / "app-data"
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.setattr(scanner, "DATA_DIR", data)
    monkeypatch.setattr(search_engine, "DATA_DIR", data)
    return data


@pytest.fixture
def sample_index(isolated_data):
    notes = {
        "Archangel Michael": {"title": "Archangel Michael", "text": "Michael is an archangel.", "links": ["God"], "summary": "An archangel."},
        "God": {"title": "God", "text": "The creator.", "links": ["Lucifer"], "summary": "Creator."},
        "Lucifer": {"title": "Lucifer", "text": "A fallen angel.", "links": [], "summary": "Fallen angel."},
    }
    isolated_data.mkdir(parents=True, exist_ok=True)
    (isolated_data / "index.json").write_text(json.dumps(notes), encoding="utf-8")
    return notes

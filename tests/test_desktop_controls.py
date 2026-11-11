import json
import time
import tkinter as tk
from tkinter import ttk

import pytest

from nemo import gui
from nemo.gui_history import HistoryWindow, PinnedWindow
from test_vault_storage import write_note
from conftest import clear_tk


@pytest.fixture
def desktop(tmp_path, monkeypatch, tk_root):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(gui, "load_settings", lambda: {"vault": {"path": str(vault)},
                                                      "ai": {"endpoint": "http://localhost:11434", "model": "test"}})
    monkeypatch.setattr(gui, "save_settings", lambda value: None)
    monkeypatch.setattr(gui.NemoDesktopApp, "_check_ollama", lambda self: None)
    root = tk_root
    app = gui.NemoDesktopApp(root)
    yield app
    app._closed = True
    app.cancel_event.set()
    clear_tk(root)


def test_stream_replaces_placeholder_and_retains_source_links(desktop):
    app = desktop
    app._begin_stream()
    app._stream_token("First ")
    app._stream_token("second [S1].")
    assert "First second" in app.transcript.get("1.0", "end")
    assert "Finding relevant" not in app.transcript.get("1.0", "end")
    evidence = {"id": "S1", "title": "Note", "path": "Note.md", "text": "An actual source.", "start_line": 1, "end_line": 1, "cited": True}
    app._finish_stream("First second [S1].", [evidence])
    text = app.transcript.get("1.0", "end")
    assert text.count("First second") == 1
    assert "[S1] Note (cited)" in text
    assert app.transcript.tag_ranges("source-link-0")


def test_stop_and_session_controls_prevent_switching_mid_answer(desktop):
    app = desktop
    app._set_busy(True)
    assert str(app.conversation_picker["state"]) == "disabled"
    assert str(app.stop_button["state"]) == "normal"
    app._stop()
    assert app.cancel_event.is_set()
    assert str(app.stop_button["state"]) == "disabled"
    app._set_busy(False)
    assert str(app.conversation_picker["state"]) == "readonly"


def test_named_conversations_switch_and_restore_their_own_messages(desktop, monkeypatch):
    app = desktop
    first = app.chat.memory.conversation_id
    app.chat.memory.add("user", "Only in the first chat")
    monkeypatch.setattr(gui.simpledialog, "askstring", lambda *args, **kwargs: "Second story")
    app._new_conversation()
    second = app.chat.memory.conversation_id
    assert second != first
    assert "Only in the first chat" not in app.transcript.get("1.0", "end")
    app.conversation_picker.current(app._conversation_ids.index(first))
    app._select_conversation()
    assert "Only in the first chat" in app.transcript.get("1.0", "end")


def test_history_search_export_and_delete_controls(desktop, tmp_path, monkeypatch):
    app = desktop
    app.chat.memory.add("user", "A city called Veloria")
    history = HistoryWindow(app)
    history.window.withdraw()
    history.query.set("Veloria")
    history.load(reset=True)
    assert len(history.rows) == 1
    export = tmp_path / "history.json"
    monkeypatch.setattr(gui.filedialog, "asksaveasfilename", lambda **kwargs: str(export))
    history.export()
    deadline = time.monotonic() + 5
    while app.busy and time.monotonic() < deadline:
        app._poll_results()
        time.sleep(0.01)
    assert json.loads(export.read_text(encoding="utf-8"))["messages"][0]["message"] == "A city called Veloria"
    monkeypatch.setattr(gui.messagebox, "askyesno", lambda *args, **kwargs: True)
    history.delete()
    assert not app.chat.memory.history
    assert not history.rows


def test_pin_controls_save_and_remove_a_user_decision(desktop):
    pins = PinnedWindow(desktop)
    pins.window.withdraw()
    pins.text.insert("1.0", "Keep the city gates silver")
    pins.label.set("Decision")
    pins.add()
    assert desktop.chat.memory.pins()[0]["content"] == "Keep the city gates silver"
    pins.list.selection_set(0)
    pins.remove()
    assert not desktop.chat.memory.pins()


def test_automatic_indexing_reloads_changed_notes(desktop):
    app = desktop
    file = write_note(app.chat.vault_path, "New.md", "First contents")
    app._watch_vault()
    deadline = time.monotonic() + 5
    while app.busy and time.monotonic() < deadline:
        app._poll_results()
        time.sleep(0.01)
    assert not app.busy
    assert app.chat.search.index["New.md"]["text"] == "First contents"
    file.write_text("Changed contents, automatically indexed")
    app._watch_vault()
    while app.busy and time.monotonic() < deadline:
        app._poll_results()
        time.sleep(0.01)
    assert app.chat.search.index["New.md"]["text"] == "Changed contents, automatically indexed"


def test_no_update_result_is_handled_without_a_missing_version_error(desktop, monkeypatch):
    messages = []
    monkeypatch.setattr(gui.messagebox, "showinfo", lambda *args, **kwargs: messages.append(args))
    desktop.results.put(("update_check", {"no_update": True}, None))
    desktop._poll_results()
    assert messages and messages[0][0] == "N.E.M.O is up to date"


def test_source_window_displays_saved_excerpt_and_does_not_open_a_different_vault(desktop):
    source = {"id": "S1", "title": "Note", "path": "Note.md", "text": "Saved evidence, not a new model quote.",
              "start_line": 3, "end_line": 4, "vault": "a different vault"}
    desktop._show_evidence(source)
    dialog = [child for child in desktop.root.winfo_children() if isinstance(child, tk.Toplevel)][-1]
    dialog.withdraw()
    button = next(child for child in dialog.winfo_children() if isinstance(child, ttk.Button))
    assert str(button["state"]) == "disabled"


def test_settings_save_model_context_and_recall_scope(desktop):
    desktop._settings_dialog()
    dialog = [child for child in desktop.root.winfo_children() if isinstance(child, tk.Toplevel)][-1]
    dialog.withdraw()
    frame = next(child for child in dialog.winfo_children() if isinstance(child, ttk.Frame))
    entries = [child for child in frame.winfo_children() if isinstance(child, ttk.Entry)]
    entries[1].delete(0, "end")
    entries[1].insert(0, "another-model")
    entries[2].delete(0, "end")
    entries[2].insert(0, "4096")
    checks = [child for child in frame.winfo_children() if isinstance(child, ttk.Checkbutton)]
    checks[1].invoke()
    next(child for child in frame.winfo_children() if isinstance(child, ttk.Button)).invoke()
    assert desktop.ai.model == "another-model" and desktop.ai.context_tokens == 4096
    assert desktop.chat.recall_all

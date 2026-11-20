from pathlib import Path
import threading
from zipfile import ZipFile

import pytest

from nemo.manuscript import Manuscript, reading_material, read_chapter, review
from nemo.gui_manuscript import ManuscriptWindow


def test_saved_book_order_edits_and_atomic_import(tmp_path):
    book = Manuscript(tmp_path)
    book.add([("Arrival", "Saw the key.\n", "first.md"), ("Return", "The key broke.", "")])
    with pytest.raises(ValueError):
        book.add([("Third", "Three", ""), ("Blank", "", "")])
    first, second = Manuscript(tmp_path).chapters()
    assert first["body"] == "Saw the key.\n"
    book.move(second["id"], -1)
    book.edit(first, "Arrival", "Saw the ring.")
    with pytest.raises(ValueError):
        book.edit(first, "Arrival", "Stale text.")
    assert [c["body"] for c in book.chapters()] == ["The key broke.", "Saw the ring."]
    book.decide("She knows", "Canon")
    book.decide("She knows", "Retired", book.decisions()[0]["id"])
    assert book.decisions()[0]["status"] == "Retired"


def test_word_import_keeps_paragraphs_and_runs(tmp_path):
    doc = tmp_path / "Arrival.docx"
    with ZipFile(doc, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello </w:t></w:r><w:r><w:t>there.</w:t></w:r></w:p><w:p><w:t>Again.</w:t></w:p></w:body></w:document>')
    assert read_chapter(doc) == "Hello there.\nAgain."


class Recorder:
    context_tokens = 2048

    def __init__(self):
        self.prompts = []

    def generate(self, prompt, **options):
        self.prompts.append(prompt)
        return "A concise review."


def test_full_reading_pass_excludes_later_prose_and_titles(tmp_path):
    book = Manuscript(tmp_path)
    book.add([("Opening", "FIRST " + "a " * 5000 + " LAST", ""), ("Second", "VISIBLE. SPOILER", ""),
              ("SECRET TITLE", "SECRET ENDING", "")])
    chapters = book.chapters()
    material = list(reading_material(chapters, chapters[1]["id"], len("VISIBLE."), "Reader"))
    ai = Recorder()
    answer = review(ai, material, "What can a reader infer?", "Reader", threading.Event(), lambda _: None)
    prompts = "\n".join(ai.prompts)
    assert all(word in prompts for word in ("FIRST", "LAST", "VISIBLE."))
    assert not any(word in prompts for word in ("SPOILER", "SECRET TITLE", "SECRET ENDING"))
    assert "condensed evidence" in answer
    assert "SECRET ENDING" in str(list(reading_material(chapters, chapters[1]["id"], None, "Author")))


def test_reader_desktop_never_fetches_vault_notes_or_canon(tmp_path, tk_root, monkeypatch):
    from types import SimpleNamespace
    import time
    from nemo import gui_manuscript
    app = SimpleNamespace(root=tk_root, ai=Recorder(), chat=SimpleNamespace(vault_path=tmp_path, search=None))
    win = ManuscriptWindow(app)
    try:
        first = tmp_path / "Chapter 2.txt"
        first.write_text("KNOWN. HIDDEN", encoding="utf-8")
        second = tmp_path / "Chapter 10.md"
        second.write_text("FUTURE", encoding="utf-8")
        monkeypatch.setattr(gui_manuscript.filedialog, "askopenfilenames", lambda **kw: [second, first])
        win.files()
        assert win.selected()["title"] == "Chapter 2"
        win.book.decide("AUTHOR_SECRET", "Canon")
        win.boundary.set("Through selected text")
        win.prose.tag_add("sel", "1.0", "1.6")
        win.ask("Does it make sense?")
        deadline = time.monotonic() + 4
        while win.running and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(.01)
        assert "A concise review" in win.answer.get("1.0", "end")
        assert "KNOWN." in app.ai.prompts[0]
        assert all(s not in app.ai.prompts[0] for s in ("HIDDEN", "FUTURE", "AUTHOR_SECRET"))
    finally:
        win.close()

"""Manuscript shelf, editorial decisions and bounded chapter reviews."""
from pathlib import Path
import queue
import re
import sqlite3
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from nemo.ai.ollama_client import GenerationCancelled
from nemo.manuscript import Manuscript, read_chapter, reading_material, review
from nemo.markup import render


class ManuscriptWindow:
    def __init__(self, app):
        self.app = app
        self.book = Manuscript(app.chat.vault_path)
        self.window = win = tk.Toplevel(app.root)
        win.title("Manuscript")
        win.geometry("980x740")
        win.transient(app.root)
        win.grab_set()
        self.cancel = threading.Event()
        self.events = queue.Queue()
        self.running = False
        win.protocol("WM_DELETE_WINDOW", self.close)
        top = ttk.Frame(win, padding=8)
        top.pack(fill="x")
        for label, action in (("Import chapters", self.files), ("Paste chapter", lambda: self.editor()),
                              ("Edit chapter", lambda: self.editor(self.selected())), ("Move up", lambda: self.move(-1)),
                              ("Move down", lambda: self.move(1)), ("Canon and drafts", self.decisions)):
            ttk.Button(top, text=label, command=lambda f=action: self.guard(f)).pack(side="left")
        pane = ttk.Panedwindow(win, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8)
        self.shelf = tk.Listbox(pane, exportselection=False, width=28)
        pane.add(self.shelf, weight=1)
        pages = ttk.Frame(pane)
        self.prose = tk.Text(pages, wrap="word", padx=12, pady=8, state="disabled")
        scroll = ttk.Scrollbar(pages, command=self.prose.yview)
        self.prose.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.prose.pack(fill="both", expand=True)
        pane.add(pages, weight=4)
        self.shelf.bind("<<ListboxSelect>>", self.preview)
        controls = ttk.Frame(win, padding=8)
        controls.pack(fill="x")
        self.view = tk.StringVar(value="Reader")
        ttk.Combobox(controls, textvariable=self.view, values=("Reader", "Author"), state="readonly", width=8).pack(side="left")
        self.boundary = tk.StringVar(value="Through chapter end")
        ttk.Combobox(controls, textvariable=self.boundary, values=("Through chapter end", "Through selected text"),
                     state="readonly", width=24).pack(side="left", padx=6)
        self.prose.configure(exportselection=False)
        ttk.Label(win, text="Reader uses earlier chapters and the selected chapter up to your boundary. Author includes the whole book, canon and matching vault notes.", wraplength=900).pack(anchor="w", padx=12)
        row = ttk.Frame(win, padding=8)
        row.pack(fill="x")
        self.question = tk.StringVar(value="Does this make sense to a first-time reader at this point?")
        ttk.Entry(row, textvariable=self.question).pack(side="left", fill="x", expand=True)
        for title, action in (("Ask", lambda: self.ask(self.question.get())),
                              ("Continuity", lambda: self.ask("Check continuity of ages, timeline, knowledge and names around the selected passage. Quote both sides of any discrepancy.")),
                              ("Summarise chapter", lambda: self.ask("Summarise the selected chapter in narrative order.", True))):
            ttk.Button(row, text=title, command=lambda f=action: self.guard(f)).pack(side="left")
        ttk.Button(row, text="Stop", command=self.cancel.set).pack(side="right")
        self.status = tk.StringVar()
        ttk.Label(win, textvariable=self.status, padding=6).pack(anchor="w")
        self.answer = tk.Text(win, wrap="word", height=10, padx=12, state="disabled")
        self.answer.pack(fill="both", expand=True, padx=8, pady=(0,8))
        self.refresh()
        self.window.after(100, self.poll)

    def guard(self, action):
        if self.running:
            self.status.set("Finish the current review or press Stop.")
            return
        try:
            action()
        except (ValueError, OSError, sqlite3.Error, StopIteration) as error:
            messagebox.showinfo("Manuscript", str(error), parent=self.window)

    def close(self):
        self.cancel.set()
        self.window.destroy()

    def refresh(self, identity=None):
        self.rows = self.book.chapters()
        self.shelf.delete(0, "end")
        for n, c in enumerate(self.rows, 1):
            self.shelf.insert("end", f"{n}. {c['title']}")
        if self.rows:
            i = next((i for i, c in enumerate(self.rows) if c["id"] == identity), 0)
            self.shelf.selection_set(i)
            self.shelf.see(i)
            self.preview()
        else:
            self.status.set("Import Markdown, plain text or Word chapters, or paste your prose.")

    def selected(self):
        if not self.shelf.curselection():
            raise ValueError("Select a chapter first.")
        return self.rows[self.shelf.curselection()[0]]

    def preview(self, event=None):
        if self.shelf.curselection():
            c = self.selected()
            self.prose.configure(state="normal")
            self.prose.delete("1.0", "end")
            self.prose.insert("1.0", c["body"])
            self.prose.configure(state="disabled")
            self.prose.yview_moveto(0)
            if not self.running:
                self.status.set(c["origin"] or "Pasted chapter")

    def files(self):
        paths = filedialog.askopenfilenames(parent=self.window, title="Import chapters in reading order",
                                            filetypes=[("Chapters", "*.md *.txt *.docx")])
        if paths:
            def natural(path):
                return [int(s) if s.isdigit() else s.casefold() for s in re.split(r"(\d+)", Path(path).name)]
            chapters = [(Path(p).stem, read_chapter(p), str(p)) for p in sorted(paths, key=natural)]
            self.book.add(chapters)
            self.refresh(self.book.chapters()[-len(chapters)]["id"])
            self.status.set(f"Saved {len(chapters)} chapter copies. Use Move up or Move down to adjust reading order.")

    def move(self, direction):
        identity = self.selected()["id"]
        self.book.move(identity, direction)
        self.refresh(identity)

    def editor(self, chapter=None):
        win = tk.Toplevel(self.window)
        win.transient(self.window)
        win.grab_set()
        win.title("Edit chapter" if chapter else "Paste chapter")
        title = tk.StringVar(value=chapter["title"] if chapter else "")
        ttk.Label(win, text="Chapter title").pack(anchor="w")
        ttk.Entry(win, textvariable=title).pack(fill="x")
        body = tk.Text(win, wrap="word", height=20, width=75)
        body.pack(fill="both", expand=True)
        if chapter:
            body.insert("1.0", chapter["body"])
        def save():
            value = body.get("1.0", "end-1c")
            if chapter:
                self.book.edit(chapter, title.get(), value)
                identity = chapter["id"]
            else:
                self.book.add([(title.get(), value, "")])
                identity = self.book.chapters()[-1]["id"]
            win.destroy()
            self.window.grab_set()
            self.refresh(identity)
        ttk.Button(win, text="Save chapter", command=lambda: self.guard(save)).pack()
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), self.window.grab_set()))

    def decisions(self):
        win = tk.Toplevel(self.window)
        win.title("Canon and drafts")
        win.transient(self.window)
        win.grab_set()
        shelf = tk.Listbox(win, width=80, exportselection=False)
        shelf.pack(fill="both", expand=True)
        state = tk.StringVar(value="Draft")
        ttk.Combobox(win, textvariable=state, values=("Canon", "Draft", "Retired"), state="readonly").pack(anchor="w")
        body = tk.Text(win, height=5, width=70, wrap="word")
        body.pack(fill="x")
        rows = []
        def refresh():
            rows[:] = self.book.decisions()
            shelf.delete(0, "end")
            for d in rows:
                shelf.insert("end", f"{d['status']} — {d['body']}")
        def select(event):
            if shelf.curselection():
                d = rows[shelf.curselection()[0]]
                state.set(d["status"])
                body.delete("1.0", "end")
                body.insert("1.0", d["body"])
        def save(update):
            if update and not shelf.curselection():
                raise ValueError("Choose a decision to update.")
            identity = rows[shelf.curselection()[0]]["id"] if update else None
            self.book.decide(body.get("1.0", "end-1c"), state.get(), identity)
            refresh()
        for label, update in (("Add decision", False), ("Update selected", True)):
            ttk.Button(win, text=label, command=lambda u=update: self.guard(lambda: save(u))).pack(side="left")
        shelf.bind("<<ListboxSelect>>", select)
        win.protocol("WM_DELETE_WINDOW", lambda: (win.destroy(), self.window.grab_set()))
        refresh()

    def ask(self, question, summary=False):
        chapter = self.selected()
        scope = self.view.get()
        offset = None
        if scope == "Reader" and self.boundary.get() == "Through selected text":
            if not self.prose.tag_ranges("sel"):
                raise ValueError("Highlight the last passage your reader has seen.")
            offset = len(self.prose.get("1.0", "sel.last"))
        material = list(reading_material(self.rows, chapter["id"], offset, scope))
        if offset is not None and not summary:
            focus_text = self.prose.get("sel.first", "sel.last")
            material.append(("Passage the reader has just reached", focus_text))
        if summary:
            material = [(label, text) for label, text in material if label.endswith(" [selected]")]
        ai = self.app.ai
        self.cancel = threading.Event()
        self.running = True
        self.shelf.configure(state="disabled")
        self.show_answer("")
        end = "through selected text" if offset is not None else "chapter end"
        heading = f"{scope} · {chapter['title']} · {end if scope == 'Reader' else 'whole manuscript'}"
        self.status.set(heading)
        def work():
            try:
                if scope == "Author" and not summary:
                    material.extend(("Author canon", d["body"]) for d in self.book.decisions() if d["status"] == "Canon")
                    notes = self.app.chat.search.retrieve(question + " " + chapter["title"], max_chars=6000,
                                                          cancel_event=self.cancel)
                    material.extend((f"Vault note {n['path']} lines {n['start_line']}-{n['end_line']}", n["text"]) for n in notes)
                answer = review(ai, material, question, scope, self.cancel,
                                lambda s: self.events.put(("progress", s)))
                self.events.put(("done", f"**{heading}**\n\n{answer}"))
            except GenerationCancelled:
                self.events.put(("done", "Review stopped."))
            except Exception as error:
                self.events.put(("done", f"Couldn't complete the review. {error}"))
        threading.Thread(target=work, daemon=True).start()

    def show_answer(self, value):
        self.answer.configure(state="normal")
        self.answer.delete("1.0", "end")
        render(self.answer, value)
        self.answer.configure(state="disabled")

    def poll(self):
        while not self.events.empty():
            kind, value = self.events.get_nowait()
            if kind == "done":
                self.running = False
                self.shelf.configure(state="normal")
                self.show_answer(value)
                self.status.set("Review finished")
            else:
                self.status.set(value)
        self.window.after(100, self.poll)

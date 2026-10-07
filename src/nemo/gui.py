"""Windows desktop interface for NEMO."""

import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlencode

import requests

from nemo.ai.chat import NemoChat
from nemo.ai.ollama_client import OllamaClient
from nemo.constellation import ConstellationWindow
from nemo.core.config import load_settings, save_settings
from nemo.core.scanner import EXCLUDED_DIRECTORIES, VaultScanner
from nemo.search.search_engine import SearchEngine
from nemo.services.router import QuestionRouter
from nemo.update_checker import check_for_update


BACKGROUND = "#101923"
SURFACE = "#182633"
TEXT = "#f1eee4"
MUTED = "#9aa9ad"
ACCENT = "#d6b46a"
SEA_GLASS = "#76b8ad"


class NemoDesktopApp:
    def __init__(self, root):
        self.root = root
        self.settings = load_settings()
        self.ai = OllamaClient(
            self.settings["ai"]["endpoint"],
            self.settings["ai"]["model"],
        )
        self.chat = NemoChat(self.ai, vault_path=self.settings["vault"].get("path", ""))
        self.results = queue.Queue()
        self.busy = False
        self.update_checking = False

        self.root.title("N.E.M.O — Narrative Engine for Mythological Organisation")
        self.root.geometry("920x640")
        self.root.minsize(700, 500)
        self.root.configure(bg=BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._configure_style()
        self._build_layout()
        self._append_message(
            "N.E.M.O",
            "Ask about your Obsidian vault, create a note, or reindex after editing notes.",
            "assistant",
        )
        self._check_ollama()
        self.root.after(120, self._poll_results)

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BACKGROUND)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Kicker.TLabel", background=BACKGROUND, foreground=SEA_GLASS, font=("Segoe UI", 8, "bold"))
        style.configure("Title.TLabel", background=BACKGROUND, foreground=ACCENT, font=("Palatino Linotype", 23, "bold"))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Accent.TButton", background=ACCENT, foreground="#1c211f", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#e5c77f"), ("disabled", "#756b50")])

    def _build_layout(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        header = ttk.Frame(self.root, padding=(24, 18, 24, 12))
        header.grid(row=0, column=0, sticky="ew")

        heading = ttk.Frame(header)
        heading.pack(side="left", fill="x", expand=True)
        ttk.Label(heading, text="✦  N.E.M.O  ✦", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            heading,
            text="THE ORACLE OF YOUR VAULT",
            style="Kicker.TLabel",
        ).pack(anchor="w", pady=(1, 0))
        ttk.Label(
            heading,
            text="A quiet guide through your world of notes",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        self.status_var = tk.StringVar(value="Checking Ollama…")
        ttk.Label(header, textvariable=self.status_var, style="Muted.TLabel").pack(side="right", padx=(12, 0))

        toolbar = ttk.Frame(self.root, padding=(24, 2, 24, 12))
        toolbar.grid(row=1, column=0, sticky="ew")
        self.vault_var = tk.StringVar(value=self._vault_label())
        ttk.Label(toolbar, textvariable=self.vault_var, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        self.vault_button = ttk.Button(toolbar, text="Choose vault", command=self._choose_vault)
        self.vault_button.pack(side="right", padx=(8, 0))
        self.reindex_button = ttk.Button(toolbar, text="Reindex", command=self._reindex)
        self.reindex_button.pack(side="right", padx=(8, 0))
        self.note_button = ttk.Button(toolbar, text="New note", command=self._new_note)
        self.note_button.pack(side="right")
        self.update_button = ttk.Button(toolbar, text="Check for updates", command=self._manual_update_check)
        self.update_button.pack(side="right", padx=(8, 0))
        self.map_button = ttk.Button(toolbar, text="Constellation", command=self._show_constellation)
        self.map_button.pack(side="right", padx=(8, 0))

        body = ttk.Frame(self.root, style="Surface.TFrame", padding=1)
        body.grid(row=2, column=0, sticky="nsew", padx=24)
        self.transcript = tk.Text(
            body,
            wrap="word",
            state="disabled",
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#36565a",
            relief="flat",
            padx=22,
            pady=20,
            font=("Segoe UI", 11),
            spacing1=3,
            spacing3=14,
        )
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scrollbar.set)
        self.transcript.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.transcript.tag_configure("assistant-name", foreground=ACCENT, font=("Palatino Linotype", 11, "bold"))
        self.transcript.tag_configure("user-name", foreground="#9db7ff", font=("Segoe UI Semibold", 10))
        self.transcript.tag_configure("message", foreground=TEXT)
        self.transcript.tag_configure("source", foreground=MUTED, font=("Segoe UI", 9))
        self.source_link_number = 0

        composer = ttk.Frame(self.root, padding=(24, 12, 24, 18))
        composer.grid(row=3, column=0, sticky="ew")
        composer_heading = ttk.Frame(composer)
        composer_heading.pack(fill="x", pady=(0, 6))
        ttk.Label(composer_heading, text="SPEAK TO N.E.M.O", style="Kicker.TLabel").pack(side="left")
        self.oracle_mode_var = tk.StringVar(value="Ask")
        self.oracle_mode_hint = tk.StringVar(value="Ask anything about your vault")
        ttk.Label(composer_heading, textvariable=self.oracle_mode_hint, style="Muted.TLabel").pack(
            side="right", padx=(10, 0)
        )
        self.oracle_mode_picker = ttk.Combobox(
            composer_heading,
            textvariable=self.oracle_mode_var,
            values=("Ask", "Find connections", "Summarize topic", "Develop idea"),
            width=19,
            state="readonly",
        )
        self.oracle_mode_picker.pack(side="right")
        self.oracle_mode_picker.bind("<<ComboboxSelected>>", self._update_oracle_hint)
        chat_bar = ttk.Frame(composer, style="Surface.TFrame", padding=(10, 6))
        chat_bar.pack(fill="x")
        self.prompt_var = tk.StringVar()
        self.prompt_entry = tk.Entry(
            chat_bar,
            textvariable=self.prompt_var,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 11),
            highlightthickness=0,
        )
        self.prompt_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(4, 12))
        self.prompt_entry.bind("<Return>", self._send_from_entry)
        self.send_button = ttk.Button(chat_bar, text="Send", style="Accent.TButton", command=self._send)
        self.send_button.pack(side="right")
        self.prompt_entry.bind("<FocusIn>", lambda _event: self.status_var.set("Type a question and press Enter to chat"))
        self.prompt_entry.focus_set()

    def _vault_label(self):
        path = self.settings.get("vault", {}).get("path", "")
        return f"Vault: {path}" if path else "Vault: choose your Obsidian folder to begin"

    def _append_message(self, speaker, message, kind, sources=None):
        self.transcript.configure(state="normal")
        name_tag = "user-name" if kind == "user" else "assistant-name"
        self.transcript.insert("end", f"{speaker}\n", name_tag)
        self.transcript.insert("end", f"{message}\n", "message")
        if sources:
            self.transcript.insert("end", "Sources · click a note to open it in Obsidian: ", "source")
            for number, source in enumerate(sources):
                if number:
                    self.transcript.insert("end", ", ", "source")
                source_text = str(source)
                source_path = Path(source_text)
                label = source_path.stem if source_path.suffix.casefold() == ".md" else source_text
                tag = f"source-link-{self.source_link_number}"
                self.source_link_number += 1
                self.transcript.tag_configure(tag, foreground=ACCENT, underline=True)
                self.transcript.tag_bind(
                    tag,
                    "<Button-1>",
                    lambda _event, reference=source_text: self._open_source(reference),
                )
                self.transcript.tag_bind(tag, "<Enter>", lambda _event: self.transcript.configure(cursor="hand2"))
                self.transcript.tag_bind(tag, "<Leave>", lambda _event: self.transcript.configure(cursor=""))
                self.transcript.insert("end", label, ("source", tag))
            self.transcript.insert("end", "\n", "source")
        self.transcript.insert("end", "\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _open_source(self, source):
        path = self._resolve_source_path(source)
        if path is None:
            messagebox.showinfo(
                "Source note not found",
                "This source is no longer in the selected vault. Reindex the vault and try again.",
                parent=self.root,
            )
            return

        uri = f"obsidian://open?{urlencode({'path': str(path)})}"
        try:
            opened = webbrowser.open(uri)
        except OSError:
            opened = False
        if not opened:
            messagebox.showinfo(
                "Couldn't open Obsidian",
                "Check that Obsidian is installed and try opening the note again.",
                parent=self.root,
            )

    def _resolve_source_path(self, source):
        vault_value = self.settings.get("vault", {}).get("path", "")
        vault = Path(vault_value).resolve() if vault_value else None
        if vault is None or not vault.is_dir():
            return None

        candidate = Path(source)
        note = None
        if not candidate.is_absolute():
            note = self.chat.search.search_by_title(str(source))
            indexed_path = note.get("path") if note else None
            if indexed_path:
                candidate = Path(indexed_path)
                if not candidate.is_absolute():
                    candidate = vault / candidate
            else:
                candidate = vault / candidate

        try:
            resolved = candidate.resolve()
            resolved.relative_to(vault)
            if resolved.is_file() and resolved.suffix.casefold() == ".md":
                return resolved
        except (OSError, ValueError):
            return None

        title = Path(str(source)).stem.casefold()
        for current, directories, filenames in os.walk(vault):
            directories[:] = [
                name for name in directories if name.casefold() not in EXCLUDED_DIRECTORIES
            ]
            for filename in filenames:
                candidate = Path(current, filename)
                if candidate.suffix.casefold() == ".md" and candidate.stem.casefold() == title:
                    return candidate.resolve()
        return None

    def _set_busy(self, busy, status=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.send_button, self.note_button, self.reindex_button, self.vault_button):
            button.configure(state=state)
        if hasattr(self, "update_button"):
            self.update_button.configure(state="disabled" if busy or self.update_checking else "normal")
        if status:
            self.status_var.set(status)

    def _run_background(self, task_name, task):
        status = "Reindexing vault…" if task_name == "reindex" else "Working…"
        self._set_busy(True, status)

        def run():
            try:
                self.results.put((task_name, task(), None))
            except Exception as error:  # show service and filesystem errors in the app
                self.results.put((task_name, None, error))

        threading.Thread(target=run, daemon=True).start()

    def _poll_results(self):
        try:
            while True:
                task_name, result, error = self.results.get_nowait()
                if task_name in ("answer", "reindex"):
                    self._set_busy(False)
                if task_name == "reindex_progress":
                    self.status_var.set(result)
                    continue
                if task_name == "update_check":
                    self.update_checking = False
                    self.update_button.configure(state="disabled" if self.busy else "normal")
                    if error:
                        if result == "manual":
                            messagebox.showinfo(
                                "Update check", "Could not check for updates. Check your internet connection and try again.", parent=self.root
                            )
                        continue
                    if result:
                        if messagebox.askyesno(
                            "N.E.M.O update available",
                            f"N.E.M.O {result['latest_version']} is available (you have {result['current_version']}).\n\nOpen the release page to download it?",
                            parent=self.root,
                        ):
                            webbrowser.open(result["url"])
                    elif isinstance(result, dict) and result.get("no_update"):
                        messagebox.showinfo("N.E.M.O is up to date", "You have the latest published version of N.E.M.O.", parent=self.root)
                    continue
                if error:
                    self.status_var.set("Needs attention")
                    self._append_message("N.E.M.O", str(error), "assistant")
                    continue
                if task_name == "connection":
                    if result == "model-ready":
                        self.status_var.set("Ready · Ollama and model connected")
                    elif result == "model-missing":
                        self.status_var.set(
                            f"Download {self.settings['ai']['model']} in Ollama first"
                        )
                    else:
                        self.status_var.set("Ollama is offline · open Ollama and try again")
                elif task_name == "answer":
                    self._append_message("N.E.M.O", result["answer"], "assistant", result.get("sources"))
                    self.status_var.set("Ready")
                elif task_name == "reindex":
                    self.chat.search = SearchEngine()
                    self.chat.router = QuestionRouter()
                    self.status_var.set("Ready · vault indexed")
                    self._append_message(
                        "N.E.M.O",
                        f"Reindex complete. Read {result['markdown']} Markdown notes."
                        + (
                            f" Skipped {result['unreadable']} inaccessible folder or file(s)."
                            if result.get("unreadable")
                            else ""
                        ),
                        "assistant",
                    )
                    self._start_update_check(manual=False)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_results)

    def _send_from_entry(self, _event):
        self._send()
        return "break"

    def _send(self, message=None):
        if self.busy:
            return
        question = (message if message is not None else self.prompt_var.get()).strip()
        if not question:
            return
        self.prompt_var.set("")
        mode = self.oracle_mode_var.get()
        display_question = question if mode == "Ask" else f"{mode} · {question}"
        self._append_message("You", display_question, "user")
        self._run_background("answer", lambda: self.chat.ask(question, mode=mode))

    def _update_oracle_hint(self, _event=None):
        hints = {
            "Ask": "Ask anything about your vault",
            "Find connections": "Enter two note titles",
            "Summarize topic": "Summarize notes about a topic",
            "Develop idea": "Explore an idea with vault context",
        }
        self.oracle_mode_hint.set(hints.get(self.oracle_mode_var.get(), hints["Ask"]))

    def _show_constellation(self):
        vault_path = self.settings.get("vault", {}).get("path", "")
        if not vault_path or not Path(vault_path).is_dir():
            messagebox.showinfo(
                "Choose your vault",
                "Choose an Obsidian vault and reindex it before opening the constellation map.",
                parent=self.root,
            )
            return
        if not self.chat.search.index or not any(
            note.get("title", key) for key, note in self.chat.search.index.items()
        ):
            messagebox.showinfo(
                "Reindex your vault",
                "Reindex your vault to build a map of its linked notes.",
                parent=self.root,
            )
            return
        ConstellationWindow(self.root, self.chat.search.index, self._open_source)

    def _new_note(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Write a new note")
        dialog.configure(bg=BACKGROUND)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.minsize(480, 360)
        dialog.geometry("580x470")

        self.root.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - 580) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - 470) // 2
        dialog.geometry(f"580x470+{max(x, 0)}+{max(y, 0)}")
        dialog.grid_columnconfigure(0, weight=1)
        dialog.grid_rowconfigure(1, weight=1)

        content = ttk.Frame(dialog, padding=20)
        content.grid(row=0, column=0, rowspan=2, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(4, weight=1)

        ttk.Label(content, text="GIVE YOUR NOTE A TITLE", style="Kicker.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        title_entry = tk.Entry(
            content,
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Segoe UI", 11),
            highlightthickness=1,
            highlightbackground="#34434a",
            highlightcolor=SEA_GLASS,
        )
        title_entry.grid(row=1, column=0, sticky="ew", ipady=8, padx=1)

        ttk.Label(content, text="WRITE YOUR NOTE", style="Kicker.TLabel").grid(
            row=2, column=0, sticky="w", pady=(16, 6)
        )
        ttk.Label(
            content,
            text="Your words are saved below the title, just as you write them.",
            style="Muted.TLabel",
        ).grid(row=3, column=0, sticky="w", pady=(0, 6))
        body_frame = ttk.Frame(content, style="Surface.TFrame", padding=1)
        body_frame.grid(row=4, column=0, sticky="nsew")
        body_frame.grid_columnconfigure(0, weight=1)
        body_frame.grid_rowconfigure(0, weight=1)
        body_text = tk.Text(
            body_frame,
            wrap="word",
            bg=SURFACE,
            fg=TEXT,
            insertbackground=TEXT,
            selectbackground="#36565a",
            relief="flat",
            padx=12,
            pady=10,
            font=("Segoe UI", 10),
        )
        body_text.grid(row=0, column=0, sticky="nsew")
        body_scrollbar = ttk.Scrollbar(body_frame, orient="vertical", command=body_text.yview)
        body_scrollbar.grid(row=0, column=1, sticky="ns")
        body_text.configure(yscrollcommand=body_scrollbar.set)

        buttons = ttk.Frame(content)
        buttons.grid(row=5, column=0, sticky="e", pady=(16, 0))

        def save():
            title = title_entry.get().strip()
            body = body_text.get("1.0", "end-1c")
            if not title:
                messagebox.showinfo("Add a title", "Give your note a title first.", parent=dialog)
                title_entry.focus_set()
                return
            if not body.strip():
                messagebox.showinfo("Write your note", "Add some content before saving.", parent=dialog)
                body_text.focus_set()
                return

            try:
                result = self.chat.save_note(title, body)
            except OSError as error:
                messagebox.showerror("Couldn't save note", str(error), parent=dialog)
                return
            self._append_message("N.E.M.O", result["answer"], "assistant", result.get("sources"))
            self.status_var.set("Ready · note saved" if result.get("sources") else "Needs attention")
            if result.get("sources"):
                dialog.destroy()

        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save note", style="Accent.TButton", command=save).pack(side="right")
        dialog.bind("<Control-Return>", lambda _event: save())
        title_entry.bind("<Return>", lambda _event: body_text.focus_set())
        title_entry.focus_set()

    def _choose_vault(self):
        current = self.settings.get("vault", {}).get("path", "")
        path = filedialog.askdirectory(
            title="Choose your Obsidian vault",
            initialdir=current if Path(current).is_dir() else str(Path.home()),
            parent=self.root,
        )
        if not path:
            return
        self.settings.setdefault("vault", {})["path"] = path
        save_settings(self.settings)
        self.chat.vault_path = Path(path)
        self.vault_var.set(self._vault_label())
        self.status_var.set("Vault selected · reindex to load its notes")

    def _reindex(self):
        vault = Path(self.settings.get("vault", {}).get("path", ""))
        if not vault.is_dir():
            messagebox.showinfo("Choose your vault", "Choose an existing Obsidian vault folder first.", parent=self.root)
            return
        scanner = VaultScanner(vault, self.ai)
        self._run_background(
            "reindex",
            lambda: scanner.scan(
                progress_callback=lambda message: self.results.put(
                    ("reindex_progress", message, None)
                )
            ),
        )

    def _manual_update_check(self):
        self._start_update_check(manual=True)

    def _start_update_check(self, manual):
        if self.update_checking:
            return
        self.update_checking = True
        self.update_button.configure(state="disabled")

        def run():
            try:
                update = check_for_update()
                no_update = {"no_update": True} if manual and update is None else None
                self.results.put(("update_check", update or no_update, None))
            except Exception as error:
                self.results.put(("update_check", "manual" if manual else None, error))

        threading.Thread(target=run, daemon=True).start()

    def _check_ollama(self):
        endpoint = self.settings["ai"]["endpoint"].rstrip("/")
        model = self.settings["ai"]["model"]

        def run():
            try:
                response = requests.get(f"{endpoint}/api/tags", timeout=3)
                response.raise_for_status()
                models = response.json().get("models", [])
                installed = any(item.get("name") == model for item in models)
                state = "model-ready" if installed else "model-missing"
            except Exception:
                state = "offline"
            self.results.put(("connection", state, None))

        threading.Thread(target=run, daemon=True).start()

    def close(self):
        self.root.destroy()


def main():
    root = tk.Tk()
    NemoDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

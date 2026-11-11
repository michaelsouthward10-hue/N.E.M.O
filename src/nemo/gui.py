"""Windows desktop interface for NEMO."""

import os
import queue
import re
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from urllib.parse import urlencode, urlparse

import requests

from nemo.ai.chat import NemoChat
from nemo.ai.ollama_client import OllamaClient
from nemo.constellation import ConstellationWindow
from nemo.core.config import load_settings, save_settings
from nemo.core.scanner import EXCLUDED_DIRECTORIES, VaultScanner, ScanCancelled
from nemo.search.search_engine import SearchEngine
from nemo.services.router import QuestionRouter
from nemo.update_checker import check_for_update
from nemo.gui_history import HistoryWindow, PinnedWindow
from nemo.version import APP_VERSION


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
            self.settings["ai"].get("context_tokens", 8192),
            self.settings["ai"].get("embedding_model", ""),
        )
        self.chat = NemoChat(self.ai, vault_path=self.settings["vault"].get("path", ""),
                             recall_all=self.settings.get("memory", {}).get("recall_other_conversations", False))
        self.results = queue.Queue()
        self.busy = False
        self.update_checking = False
        self.cancel_event = threading.Event()
        self._request_number = 0
        self._closed = False
        self._auto_index_paused = False
        self._streaming = False

        self.root.title(f"N.E.M.O {APP_VERSION} — Narrative Engine for Mythological Organisation")
        self.root.geometry("1040x760")
        self.root.minsize(860, 600)
        self.root.configure(bg=BACKGROUND)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self._configure_style()
        self._build_layout()
        self._append_message(
            "N.E.M.O",
            "Ask about your Obsidian vault, create a note, or reindex after editing notes.",
            "assistant",
        )
        self._restore_conversation()
        self._refresh_conversations()
        self._check_ollama()
        self.root.after(120, self._poll_results)
        self.root.after(1500, self._watch_vault)

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=BACKGROUND)
        style.configure("Surface.TFrame", background=SURFACE)
        style.configure("TLabel", background=BACKGROUND, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Kicker.TLabel", background=BACKGROUND, foreground=SEA_GLASS, font=("Segoe UI", 8, "bold"))
        style.configure("Title.TLabel", background=BACKGROUND, foreground=ACCENT, font=("Palatino Linotype", 23, "bold"))
        style.configure("Reindex.TLabel", foreground=SEA_GLASS, font=("Segoe UI", 11, "bold"))
        style.configure("Reindex.Horizontal.TProgressbar", background=SEA_GLASS, troughcolor=SURFACE)
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Accent.TButton", background=ACCENT, foreground="#1c211f", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#e5c77f"), ("disabled", "#756b50")])

    def _build_layout(self):
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

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
        vault_row = ttk.Frame(toolbar)
        vault_row.pack(fill="x")
        ttk.Label(vault_row, textvariable=self.vault_var, style="Muted.TLabel", wraplength=450).pack(side="left", fill="x", expand=True)
        self.vault_button = ttk.Button(vault_row, text="Choose vault", command=self._choose_vault)
        self.vault_button.pack(side="right", padx=(8, 0))
        self.reindex_button = ttk.Button(vault_row, text="Reindex", command=self._reindex)
        self.reindex_button.pack(side="right", padx=(8, 0))
        self.note_button = ttk.Button(vault_row, text="New note", command=self._new_note)
        self.note_button.pack(side="right")
        chat_row = ttk.Frame(toolbar)
        chat_row.pack(fill="x", pady=(8, 0))
        self.conversation_var = tk.StringVar()
        self.conversation_picker = ttk.Combobox(chat_row, textvariable=self.conversation_var, state="readonly", width=25)
        self.conversation_picker.pack(side="left", fill="x", expand=True)
        self.conversation_picker.bind("<<ComboboxSelected>>", self._select_conversation)
        self.new_chat_button = ttk.Button(chat_row, text="New chat", command=self._new_conversation)
        self.new_chat_button.pack(side="left", padx=(8, 0))
        self.rename_chat_button = ttk.Button(chat_row, text="Rename", command=self._rename_conversation)
        self.rename_chat_button.pack(side="left", padx=(8, 0))
        self.history_button = ttk.Button(chat_row, text="Chat log", command=self._show_chat_log)
        self.history_button.pack(side="left", padx=(8, 0))
        self.pins_button = ttk.Button(chat_row, text="Pinned", command=lambda: PinnedWindow(self))
        self.pins_button.pack(side="left", padx=(8, 0))
        self.more_button = ttk.Menubutton(chat_row, text="More")
        menu = tk.Menu(self.more_button, tearoff=False)
        menu.add_command(label="Constellation", command=self._show_constellation)
        menu.add_command(label="AI and indexing settings", command=self._settings_dialog)
        menu.add_command(label="Check for updates", command=self._manual_update_check)
        self.more_button.configure(menu=menu)
        self.more_button.pack(side="right", padx=(8, 0))

        self.reindex_panel = ttk.Frame(self.root, padding=(24, 0, 24, 12))
        self.reindex_panel.grid(row=2, column=0, sticky="ew")
        self.reindex_heading = tk.StringVar(value="Reindexing vault")
        self.reindex_detail = tk.StringVar(value="Finding Markdown notes…")
        ttk.Label(self.reindex_panel, textvariable=self.reindex_heading, style="Reindex.TLabel").pack(anchor="w")
        ttk.Label(self.reindex_panel, textvariable=self.reindex_detail, style="Muted.TLabel", wraplength=780).pack(anchor="w", pady=(3, 6))
        self.reindex_progress = ttk.Progressbar(self.reindex_panel, mode="indeterminate", style="Reindex.Horizontal.TProgressbar")
        self.reindex_progress.pack(fill="x")
        self.reindex_panel.grid_remove()

        body = ttk.Frame(self.root, style="Surface.TFrame", padding=1)
        body.grid(row=3, column=0, sticky="nsew", padx=24)
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
        composer.grid(row=4, column=0, sticky="ew")
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
        self.stop_button = ttk.Button(chat_bar, text="Stop", command=self._stop, state="disabled")
        self.stop_button.pack(side="right", padx=(0, 8))
        self.prompt_entry.bind("<FocusIn>", lambda _event: self.status_var.set("Type a question and press Enter to chat"))
        self.prompt_entry.focus_set()

    def _refresh_conversations(self):
        conversations = self.chat.memory.conversations()
        self._conversation_ids = [item["id"] for item in conversations]
        labels = [f"{item['title']} ({item['messages']})" for item in conversations]
        self.conversation_picker.configure(values=labels)
        if self.chat.memory.conversation_id in self._conversation_ids:
            self.conversation_picker.current(self._conversation_ids.index(self.chat.memory.conversation_id))

    def _select_conversation(self, event=None):
        if not self.busy and self.conversation_picker.current() >= 0:
            self.chat.memory.select_conversation(self._conversation_ids[self.conversation_picker.current()])
            self._restore_conversation()

    def _new_conversation(self):
        if self.busy:
            return
        title = simpledialog.askstring("New conversation", "Conversation name:", parent=self.root)
        if title:
            self.chat.memory.new_conversation(title)
            self._refresh_conversations()
            self._restore_conversation()

    def _rename_conversation(self):
        if self.busy:
            return
        title = simpledialog.askstring("Rename conversation", "New name:", parent=self.root)
        if title and title.strip():
            self.chat.memory.rename_conversation(title)
            self._refresh_conversations()

    def _vault_label(self):
        path = self.settings.get("vault", {}).get("path", "")
        return f"Vault: {path}" if path else "Vault: choose your Obsidian folder to begin"

    def _append_message(self, speaker, message, kind, sources=None):
        self.transcript.configure(state="normal")
        name_tag = "user-name" if kind == "user" else "assistant-name"
        self.transcript.insert("end", f"{speaker}\n", name_tag)
        body_start = self.transcript.index("end-1c")
        self.transcript.insert("end", f"{message}\n", "message")
        if sources:
            self.transcript.insert("end", "Sources · click a note to open it in Obsidian: ", "source")
            for number, source in enumerate(sources):
                if number:
                    self.transcript.insert("end", ", ", "source")
                source_text = source["path"] if isinstance(source, dict) else str(source)
                source_path = Path(source_text)
                label = source_path.stem if source_path.suffix.casefold() == ".md" else source_text
                if isinstance(source, dict):
                    label = f"[{source['id']}] {source['title']} ({'cited' if source.get('cited') else 'retrieved'})"
                tag = f"source-link-{self.source_link_number}"
                self.source_link_number += 1
                self.transcript.tag_configure(tag, foreground=ACCENT, underline=True)
                self.transcript.tag_bind(
                    tag,
                    "<Button-1>",
                    lambda _event, reference=source: self._show_evidence(reference) if isinstance(reference, dict) else self._open_source(str(reference)),
                )
                self.transcript.tag_bind(tag, "<Enter>", lambda _event: self.transcript.configure(cursor="hand2"))
                self.transcript.tag_bind(tag, "<Leave>", lambda _event: self.transcript.configure(cursor=""))
                self.transcript.insert("end", label, ("source", tag))
                if isinstance(source, dict):
                    for match in re.finditer(r"\[" + re.escape(source["id"]) + r"\]", message):
                        self.transcript.tag_add(tag, f"{body_start}+{match.start()}c", f"{body_start}+{match.end()}c")
            self.transcript.insert("end", "\n", "source")
        self.transcript.insert("end", "\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _show_evidence(self, source):
        dialog = tk.Toplevel(self.root)
        dialog.title(f"[{source['id']}] {source['title']}")
        dialog.geometry("780x520")
        ttk.Label(dialog, text=f"{source['path']} - lines {source['start_line']}-{source['end_line']}", padding=12, wraplength=730).pack(anchor="w")
        ttk.Label(dialog, text="Saved passage supplied with this answer. The current note may have changed.", padding=(12, 0)).pack(anchor="w")
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", padx=12, pady=12)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        text.insert("end", source["text"])
        text.configure(state="disabled")
        same_vault = not source.get("vault") or source["vault"] == str(self.chat.vault_path.resolve()).casefold()
        ttk.Button(dialog, text="Open current note in Obsidian", command=lambda: self._open_source(source["path"]),
                   state="normal" if same_vault else "disabled").pack(anchor="e", padx=12, pady=(0, 12))

    def _begin_stream(self):
        self._streaming = True
        self._stream_started = False
        self.transcript.configure(state="normal")
        self.transcript.mark_set("stream-anchor", "end-1c")
        self.transcript.mark_gravity("stream-anchor", "left")
        self.transcript.insert("end", "N.E.M.O\n", "assistant-name")
        self.transcript.mark_set("stream-body", "end-1c")
        self.transcript.mark_gravity("stream-body", "left")
        self.transcript.insert("end", "Finding relevant notes and earlier discussions...\n\n", "source")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _stream_token(self, text):
        if not self._streaming:
            return
        self.transcript.configure(state="normal")
        if not self._stream_started:
            self.transcript.delete("stream-body", "end-1c")
            self._stream_started = True
        self.transcript.insert("end", text, "message")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _finish_stream(self, answer, sources=None):
        if self._streaming:
            self.transcript.configure(state="normal")
            self.transcript.delete("stream-anchor", "end-1c")
            self.transcript.configure(state="disabled")
        self._streaming = False
        self._append_message("N.E.M.O", answer, "assistant", sources)

    def _stop(self):
        if self.busy:
            self.cancel_event.set()
            self.stop_button.configure(state="disabled")
            self.status_var.set("Stopping...")

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

        if Path(str(source)).is_absolute() or "/" in str(source) or "\\" in str(source) or Path(str(source)).suffix.casefold() == ".md":
            return None

        title = Path(str(source)).stem.casefold()
        matches = []
        for current, directories, filenames in os.walk(vault):
            directories[:] = [
                name for name in directories if name.casefold() not in EXCLUDED_DIRECTORIES
            ]
            for filename in filenames:
                candidate = Path(current, filename)
                if candidate.suffix.casefold() == ".md" and candidate.stem.casefold() == title:
                    try:
                        resolved = candidate.resolve()
                        resolved.relative_to(vault)
                        matches.append(resolved)
                    except (OSError, ValueError):
                        pass
        return matches[0] if len(matches) == 1 else None

    def _set_busy(self, busy, status=None):
        self.busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.send_button, self.note_button, self.reindex_button, self.vault_button,
                       self.new_chat_button, self.rename_chat_button, self.history_button, self.pins_button, self.more_button):
            button.configure(state=state)
        self.conversation_picker.configure(state="disabled" if busy else "readonly")
        self.stop_button.configure(state="normal" if busy else "disabled")
        if status:
            self.status_var.set(status)

    def _run_background(self, task_name, task):
        self.cancel_event = threading.Event()
        self._active_task = task_name
        status = {"reindex": "Reindexing vault...", "auto_index": "Updating changed notes...", "summarize": "Summarizing earlier discussion...", "export": "Exporting conversation..."}.get(task_name, "Working...")
        self._set_busy(True, status)

        def run():
            try:
                self.results.put((task_name, task(), None))
            except Exception as error:  # show service and filesystem errors in the app
                self.results.put((task_name, None, error))

        threading.Thread(target=run, daemon=True).start()

    def _poll_results(self):
        if self._closed:
            return
        try:
            while True:
                task_name, result, error = self.results.get_nowait()
                if task_name == "answer_token":
                    number, token = result
                    if number == self._request_number:
                        self._stream_token(token)
                    continue
                if task_name in ("answer", "reindex", "auto_index", "summarize", "export"):
                    self._set_busy(False)
                if task_name == "reindex_progress":
                    self._update_reindex_progress(result)
                    continue
                if task_name == "update_check":
                    self.update_checking = False
                    if error:
                        if result == "manual":
                            messagebox.showinfo(
                                "Update check", "Could not check for updates. Check your internet connection and try again.", parent=self.root
                            )
                        continue
                    if result and not result.get("no_update"):
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
                    if task_name == "export" and getattr(self, "_export_window", None) and self._export_window.window.winfo_exists():
                        self._export_window.info.set(str(error))
                    if task_name == "reindex":
                        self._finish_reindex(error=error)
                    elif task_name == "auto_index":
                        self._auto_index_paused = True
                    if task_name == "answer":
                        self._finish_stream((getattr(error, "partial", "") + f"\n\nCouldn't complete the reply: {error}").strip())
                        self._refresh_conversations()
                    else:
                        self._append_message("N.E.M.O", str(error), "assistant")
                    self.status_var.set("Needs attention")
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
                    sources = result.get("evidence") or result.get("sources")
                    answer = result["answer"]
                    if result.get("warnings"):
                        answer += "\n\n" + "\n".join(result["warnings"])
                    self._finish_stream(answer, sources)
                    self._refresh_conversations()
                    self.status_var.set("Stopped" if result.get("stopped") else "Ready")
                elif task_name == "reindex":
                    self.chat.refresh_index()
                    self._auto_index_paused = False
                    self._finish_reindex(result)
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
                elif task_name == "auto_index":
                    self.chat.refresh_index()
                    updates = result.get("changed", 0) + result.get("removed", 0)
                    self.status_var.set(f"Ready - {updates} note changes indexed" if updates else "Ready - notes up to date")
                    if result.get("unreadable"):
                        self.status_var.set(f"Notes updated; {result['unreadable']} inaccessible files or folders kept for retry")
                elif task_name == "summarize":
                    self.status_var.set("Earlier discussion summary updated" if result else "No older messages need summarizing yet")
                elif task_name == "export":
                    self.status_var.set("Conversation exported")
                    if getattr(self, "_export_window", None) and self._export_window.window.winfo_exists():
                        self._export_window.info.set("Conversation exported.")
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
        self._request_number += 1
        number = self._request_number
        self._begin_stream()
        self._run_background("answer", lambda: self.chat.ask(
            question, mode=mode, cancel_event=self.cancel_event,
            on_token=lambda token: self.results.put(("answer_token", (number, token), None))))

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

    def _restore_conversation(self):
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        self.transcript.configure(state="disabled")
        for item in self.chat.memory.recent(40):
            role = item["role"]
            self._append_message("You" if role == "user" else "N.E.M.O", item["message"], role, item.get("sources"))
        self._append_message("N.E.M.O", "This conversation is saved for the selected vault. Use Chat log to search or export it, and Pinned to keep facts or decisions in context.", "assistant")
        if getattr(self.chat.search, "warning", ""):
            self._append_message("N.E.M.O", self.chat.search.warning, "assistant")

    def _show_chat_log(self):
        if not self.busy:
            HistoryWindow(self)

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
        self.reindex_panel.grid_remove()
        self.chat.set_vault(path)
        self._auto_index_paused = False
        self._refresh_conversations()
        self._restore_conversation()
        self.vault_var.set(self._vault_label())
        self.status_var.set("Vault selected · reindex to load its notes")

    def _begin_reindex(self):
        self.reindex_panel.grid()
        self.reindex_heading.set("Reindexing vault")
        self.reindex_detail.set("Finding Markdown notes…")
        self.reindex_progress.stop()
        self.reindex_progress.configure(mode="indeterminate", maximum=100, value=0)
        self.reindex_progress.start(15)

    def _update_reindex_progress(self, progress):
        self.status_var.set(progress["message"])
        self.reindex_detail.set(progress["message"])
        if progress["phase"] != "discovering":
            self.reindex_progress.stop()
            self.reindex_progress.configure(mode="determinate", maximum=max(1, progress["total"]), value=progress["completed"])
            self.reindex_heading.set("Saving index…" if progress["phase"] == "saving" else "Reindexing vault")

    def _finish_reindex(self, result=None, error=None):
        self.reindex_progress.stop()
        if error is not None:
            self.reindex_heading.set("Reindex stopped" if isinstance(error, ScanCancelled) else "Reindex failed")
            self.reindex_detail.set(str(error))
            return
        self.reindex_progress.configure(mode="determinate", maximum=1, value=1)
        self.reindex_heading.set("Reindex complete")
        detail = f"Finished scanning {result['scanned']} Markdown notes · {result['markdown']} notes indexed."
        if result.get("unreadable"):
            detail += f" Skipped {result['unreadable']} inaccessible folder or file(s)."
        self.reindex_detail.set(detail)

    def _reindex(self):
        vault = Path(self.settings.get("vault", {}).get("path", ""))
        if not vault.is_dir():
            messagebox.showinfo("Choose your vault", "Choose an existing Obsidian vault folder first.", parent=self.root)
            return
        self._begin_reindex()
        scanner = VaultScanner(vault, self.ai)
        self._run_background(
            "reindex",
            lambda: scanner.scan(
                cancel_event=self.cancel_event,
                metrics_callback=lambda progress: self.results.put(
                    ("reindex_progress", progress, None)
                )
            ),
        )

    def _manual_update_check(self):
        self._start_update_check(manual=True)

    def _start_update_check(self, manual):
        if self.update_checking:
            return
        self.update_checking = True

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
        self._closed = True
        self.cancel_event.set()
        self.root.destroy()

    def _watch_vault(self):
        if self._closed:
            return
        indexing = self.settings.get("indexing", {})
        if indexing.get("automatic", True) and not self.busy and not self._auto_index_paused:
            vault = self.settings.get("vault", {}).get("path", "")
            if vault and Path(vault).is_dir():
                scanner = VaultScanner(vault)
                self._run_background("auto_index", lambda: scanner.scan(incremental=True, cancel_event=self.cancel_event))
        try:
            interval = max(5, int(indexing.get("interval_seconds", 10)))
        except (TypeError, ValueError):
            interval = 10
        self.root.after(interval * 1000, self._watch_vault)

    def _settings_dialog(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("AI and indexing settings")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.geometry("650x560")
        frame = ttk.Frame(dialog, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        values = {}
        ai = self.settings["ai"]
        for row, (name, label, initial) in enumerate((
            ("endpoint", "Ollama endpoint", ai["endpoint"]),
            ("model", "Conversation model", ai["model"]),
            ("context_tokens", "Context size", str(ai.get("context_tokens", 8192))),
            ("embedding_model", "Embedding model (optional)", ai.get("embedding_model", "")),
        )):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=8)
            values[name] = tk.StringVar(value=initial)
            ttk.Entry(frame, textvariable=values[name]).grid(row=row, column=1, sticky="ew", pady=8)
        ttk.Label(frame, text="Question expansion uses the conversation model. Optional embedding search needs an embedding model already downloaded in Ollama. Its first search builds a local cache and can take longer. Leave blank to use word ranking and model-generated search terms.", wraplength=590).grid(row=4, column=0, columnspan=2, sticky="w", pady=12)
        automatic = tk.BooleanVar(value=self.settings.get("indexing", {}).get("automatic", True))
        ttk.Checkbutton(frame, text="Automatically index added, changed and deleted notes", variable=automatic).grid(row=5, column=0, columnspan=2, sticky="w", pady=8)
        other_chats = tk.BooleanVar(value=self.settings.get("memory", {}).get("recall_other_conversations", False))
        ttk.Checkbutton(frame, text="Allow recall from other conversations in this vault", variable=other_chats).grid(row=6, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(frame, text="Context size: 2,048 to 32,768 tokens. Larger values use more memory. Nothing is downloaded automatically.", wraplength=590).grid(row=7, column=0, columnspan=2, sticky="w", pady=8)

        def save():
            try:
                endpoint = values["endpoint"].get().strip().rstrip("/")
                if urlparse(endpoint).scheme not in {"http", "https"} or not urlparse(endpoint).netloc:
                    raise ValueError("Enter a valid HTTP or HTTPS Ollama endpoint.")
                model = values["model"].get().strip()
                if not model:
                    raise ValueError("Choose a conversation model.")
                context = int(values["context_tokens"].get())
                if not 2048 <= context <= 32768:
                    raise ValueError("Context size must be between 2,048 and 32,768 tokens.")
                self.settings["ai"].update(endpoint=endpoint, model=model, context_tokens=context,
                                           embedding_model=values["embedding_model"].get().strip())
                self.settings.setdefault("indexing", {})["automatic"] = automatic.get()
                self.settings.setdefault("memory", {})["recall_other_conversations"] = other_chats.get()
                save_settings(self.settings)
                self.ai = OllamaClient(endpoint, model, context, self.settings["ai"]["embedding_model"])
                self.chat.ai = self.ai
                self.chat.recall_all = other_chats.get()
                self.chat.semantic = self.chat._make_semantic(self.chat.vault_path)
                self._auto_index_paused = False
                self._check_ollama()
                dialog.destroy()
            except (ValueError, OSError) as error:
                messagebox.showinfo("Couldn't save settings", str(error), parent=dialog)
        ttk.Button(frame, text="Save settings", command=save, style="Accent.TButton").grid(row=8, column=1, sticky="e", pady=12)


def main():
    root = tk.Tk()
    NemoDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

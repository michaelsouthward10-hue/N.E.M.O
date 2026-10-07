"""Windows desktop interface for NEMO."""

from pathlib import Path
import queue
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

import requests

from nemo.ai.chat import NemoChat
from nemo.ai.ollama_client import OllamaClient
from nemo.core.config import load_settings, save_settings
from nemo.core.scanner import VaultScanner
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

        composer = ttk.Frame(self.root, padding=(24, 12, 24, 18))
        composer.grid(row=3, column=0, sticky="ew")
        ttk.Label(composer, text="SPEAK TO N.E.M.O", style="Kicker.TLabel").pack(anchor="w", pady=(0, 6))
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
            self.transcript.insert("end", f"Sources: {', '.join(map(str, sources))}\n", "source")
        self.transcript.insert("end", "\n")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

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
        self._append_message("You", question, "user")
        self._run_background("answer", lambda: self.chat.ask(question))

    def _new_note(self):
        title = simpledialog.askstring("Create a note", "What should the note be called?", parent=self.root)
        if title and title.strip():
            self._send(f"new note: {title.strip()}")

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

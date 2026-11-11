"""Conversation management and pinned context controls."""
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


class HistoryWindow:
    def __init__(self, app):
        self.app = app
        self.memory = app.chat.memory
        self.window = tk.Toplevel(app.root)
        self.window.title("Saved conversations")
        self.window.geometry("900x700")
        self.window.minsize(760, 480)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)
        self.window.rowconfigure(3, weight=2)
        self.before = None
        self.rows = {}
        self.query = tk.StringVar()
        self.all_chats = tk.BooleanVar(value=False)
        top = ttk.Frame(self.window, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(0, weight=1)
        entry = ttk.Entry(top, textvariable=self.query)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda event: self.load(reset=True))
        ttk.Button(top, text="Search", command=lambda: self.load(reset=True)).grid(row=0, column=1)
        ttk.Checkbutton(top, text="All conversations", variable=self.all_chats, command=lambda: self.load(reset=True)).grid(row=0, column=2, padx=8)
        controls = ttk.Frame(self.window, padding=(12, 0, 12, 8))
        controls.grid(row=1, column=0, sticky="ew")
        ttk.Button(controls, text="Older messages", command=self.load).pack(side="left")
        ttk.Button(controls, text="Open conversation", command=self.open_conversation).pack(side="left", padx=5)
        ttk.Button(controls, text="Export current chat", command=self.export).pack(side="left", padx=5)
        ttk.Button(controls, text="Delete active chat", command=self.delete).pack(side="right")
        frame = ttk.Frame(self.window, padding=(12, 0))
        frame.grid(row=2, column=0, sticky="nsew")
        self.tree = ttk.Treeview(frame, columns=("time", "chat", "role", "excerpt"), show="headings", selectmode="browse")
        for key, title, width in (("time", "Time (UTC)", 140), ("chat", "Conversation", 160), ("role", "Speaker", 85), ("excerpt", "Message", 390)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, stretch=key == "excerpt")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.preview)
        body = ttk.Frame(self.window, padding=(12, 8))
        body.grid(row=3, column=0, sticky="nsew")
        self.text = tk.Text(body, wrap="word", state="disabled", padx=10, pady=10)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        self.text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        footer = ttk.Frame(self.window, padding=12)
        footer.grid(row=4, column=0, sticky="ew")
        self.info = tk.StringVar()
        ttk.Label(footer, textvariable=self.info, wraplength=680).pack(anchor="w")
        ttk.Button(footer, text="Pinned facts and decisions", command=lambda: PinnedWindow(app)).pack(side="left", pady=(8, 0))
        ttk.Button(footer, text="Refresh summary", command=self.summarize).pack(side="left", padx=8, pady=(8, 0))
        self.load(reset=True)

    def load(self, reset=False):
        if self.app.busy and getattr(self.app, "_active_task", "") == "export":
            self.info.set("Exporting the conversation. Please wait or press Stop.")
            return
        if reset:
            self.before = None
            self.rows = {}
            self.tree.delete(*self.tree.get_children())
        items = self.memory.page(before=self.before, query=self.query.get(), all_conversations=self.all_chats.get())
        titles = {item["id"]: item["title"] for item in self.memory.conversations()}
        for item in items:
            identity = str(item["id"])
            self.rows[identity] = item
            self.tree.insert("", "end", iid=identity, values=(item["created_at"], titles.get(item["conversation_id"], ""),
                                                             item["role"], item["message"].replace("\n", " ")[:130]))
        if items:
            self.before = items[-1]["id"]
        self.info.set(f"Showing {len(self.rows)} messages, newest first. " + ("No older matches." if not items else "Use Older messages to browse further."))
        if reset:
            self._set_text("Saved summary (AI-generated; review against the original messages):\n\n" +
                           (self.memory.summary()["summary"] or "No summary yet. Long discussions are summarized automatically."))

    def _set_text(self, text):
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("end", text)
        self.text.configure(state="disabled")

    def preview(self, event=None):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.rows[selected[0]]
        self._set_text(f"{item['role'].capitalize()} - {item['created_at']} UTC - {item['status']}\n\n{item['message']}")
        self.text.configure(state="normal")
        for source in item["sources"]:
            if not isinstance(source, dict):
                continue
            tag = "evidence-" + source["id"]
            self.text.insert("end", f"\n\n[{source['id']}] {source['path']} (lines {source['start_line']}-{source['end_line']})", tag)
            self.text.tag_configure(tag, foreground="#276e89", underline=True)
            self.text.tag_bind(tag, "<Button-1>", lambda event, value=source: self.app._show_evidence(value))
        self.text.configure(state="disabled")

    def open_conversation(self):
        if self.memory is not self.app.chat.memory:
            messagebox.showinfo("Vault changed", "Reopen Chat log for the selected vault.", parent=self.window)
            return
        if self.app.busy:
            messagebox.showinfo("Finish the current task", "Wait for the current task or press Stop before switching conversations.", parent=self.window)
            return
        selected = self.tree.selection()
        if selected:
            self.memory.select_conversation(self.rows[selected[0]]["conversation_id"])
            self.app._refresh_conversations()
            self.app._restore_conversation()
            self.load(reset=True)

    def export(self):
        if self.memory is not self.app.chat.memory:
            messagebox.showinfo("Vault changed", "Reopen Chat log for the selected vault.", parent=self.window)
            return
        if self.app.busy:
            return
        path = filedialog.asksaveasfilename(parent=self.window, title="Export current conversation", defaultextension=".md",
                                          filetypes=[("Markdown", "*.md"), ("JSON", "*.json")])
        if path:
            try:
                self.app._export_window = self
                self.app._run_background("export", lambda: self.memory.export(path, self.app.cancel_event))
                self.info.set("Exporting the conversation. Please wait or press Stop.")
            except OSError as error:
                messagebox.showerror("Couldn't export", str(error), parent=self.window)

    def delete(self):
        if self.memory is not self.app.chat.memory:
            messagebox.showinfo("Vault changed", "Reopen Chat log for the selected vault.", parent=self.window)
            return
        if self.app.busy:
            messagebox.showinfo("Finish the current task", "Wait for the current task or press Stop first.", parent=self.window)
            return
        current = next(item for item in self.memory.conversations() if item["id"] == self.memory.conversation_id)
        if not messagebox.askyesno("Delete this conversation?", f"Delete '{current['title']}', including all its messages, its summary, and its pinned context? This cannot be undone. Export a copy first if you want to keep it.", parent=self.window):
            return
        self.memory.delete_conversation()
        if self.app.chat.semantic:
            self.app.chat.semantic.clear()
        self.app._refresh_conversations()
        self.app._restore_conversation()
        self.load(reset=True)

    def summarize(self):
        if self.app.busy or self.memory is not self.app.chat.memory:
            return
        self.app._run_background("summarize", lambda: self.memory.summarize(self.app.ai, self.app.cancel_event, force=True))


class PinnedWindow:
    def __init__(self, app):
        self.app = app
        self.memory = app.chat.memory
        self.conversation_id = self.memory.conversation_id
        self.window = tk.Toplevel(app.root)
        self.window.title("Pinned facts, decisions and ideas")
        self.window.geometry("680x510")
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)
        ttk.Label(self.window, text="Pins apply to this conversation. A pinned fact is your assertion, not automatic verification against notes.",
                  wraplength=630, padding=12).grid(row=0, column=0, sticky="ew")
        self.list = tk.Listbox(self.window)
        self.list.grid(row=1, column=0, sticky="nsew", padx=12)
        self.label = tk.StringVar(value="Decision")
        ttk.Combobox(self.window, values=("Fact", "Decision", "Idea"), textvariable=self.label, state="readonly").grid(row=2, column=0, sticky="w", padx=12, pady=8)
        self.text = tk.Text(self.window, height=6, wrap="word")
        self.text.grid(row=3, column=0, sticky="ew", padx=12)
        controls = ttk.Frame(self.window, padding=12)
        controls.grid(row=4, column=0, sticky="ew")
        ttk.Button(controls, text="Pin this", command=self.add).pack(side="left")
        ttk.Button(controls, text="Remove selected pin", command=self.remove).pack(side="right")
        self.list.bind("<<ListboxSelect>>", self.preview)
        self.load()

    def load(self):
        self.items = self.memory.pins()
        self.list.delete(0, "end")
        for item in self.items:
            self.list.insert("end", f"{item['label']}: {item['content']}")

    def valid(self):
        if self.app.busy or self.memory is not self.app.chat.memory or self.memory.conversation_id != self.conversation_id:
            messagebox.showinfo("Conversation changed", "Finish the current task and reopen pins for the active conversation.", parent=self.window)
            return False
        return True

    def add(self):
        if not self.valid():
            return
        try:
            self.memory.pin(self.text.get("1.0", "end-1c"), self.label.get())
            self.text.delete("1.0", "end")
            self.load()
        except ValueError as error:
            messagebox.showinfo("Couldn't pin", str(error), parent=self.window)

    def remove(self):
        if self.valid() and self.list.curselection():
            self.memory.unpin(self.items[self.list.curselection()[0]]["id"])
            self.load()

    def preview(self, event=None):
        if self.list.curselection():
            item = self.items[self.list.curselection()[0]]
            self.text.delete("1.0", "end")
            self.text.insert("end", item["content"])
            self.label.set(item["label"])

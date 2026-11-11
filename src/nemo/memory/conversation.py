"""Persistent conversations, searchable recall, summaries and user-pinned decisions."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import threading
import tempfile
import uuid

from nemo.core.storage import vault_key
from nemo.search.ranking import Ranker, terms


class ConversationMemory:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._temporary = sqlite3.connect(":memory:", check_same_thread=False) if not self.path else None
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
            for name, definition in {"conversation_id": "TEXT NOT NULL DEFAULT 'default'", "status": "TEXT NOT NULL DEFAULT 'complete'", "sources": "TEXT NOT NULL DEFAULT '[]'"}.items():
                if name not in columns:
                    db.execute(f"ALTER TABLE messages ADD COLUMN {name} {definition}")
            db.execute("CREATE TABLE IF NOT EXISTS conversations (id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP, summary TEXT NOT NULL DEFAULT '', summary_until INTEGER NOT NULL DEFAULT 0)")
            if not db.execute("SELECT 1 FROM conversations LIMIT 1").fetchone() or db.execute("SELECT 1 FROM messages WHERE conversation_id='default' LIMIT 1").fetchone():
                db.execute("INSERT OR IGNORE INTO conversations(id,title) VALUES ('default','Main conversation')")
            db.execute("CREATE TABLE IF NOT EXISTS preferences (name TEXT PRIMARY KEY, value TEXT)")
            db.execute("CREATE TABLE IF NOT EXISTS pins (id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, label TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
            db.execute("CREATE INDEX IF NOT EXISTS message_conversation ON messages(conversation_id,id)")
            row = db.execute("SELECT id FROM conversations ORDER BY updated_at DESC, rowid DESC LIMIT 1").fetchone()
            self.conversation_id = row[0]
            saved = db.execute("SELECT value FROM preferences WHERE name='active_conversation'").fetchone()
            if saved and db.execute("SELECT 1 FROM conversations WHERE id=?", (saved[0],)).fetchone():
                self.conversation_id = saved[0]
            self.fts = False
            try:
                exists = db.execute("SELECT 1 FROM sqlite_master WHERE name='message_search'").fetchone()
                db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS message_search USING fts5(message,content='messages',content_rowid='id',tokenize='porter unicode61')")
                db.execute("CREATE TRIGGER IF NOT EXISTS messages_insert AFTER INSERT ON messages BEGIN INSERT INTO message_search(rowid,message) VALUES(new.id,new.message); END")
                db.execute("CREATE TRIGGER IF NOT EXISTS messages_delete AFTER DELETE ON messages BEGIN INSERT INTO message_search(message_search,rowid,message) VALUES('delete',old.id,old.message); END")
                if not exists:
                    db.execute("INSERT INTO message_search(message_search) VALUES('rebuild')")
                self.fts = True
            except sqlite3.OperationalError:
                pass

    @classmethod
    def for_vault(cls, vault_path):
        from nemo.core.paths import DATA_DIR
        key = vault_key(vault_path) if vault_path else "_general"
        return cls(DATA_DIR / "conversations" / f"{key}.sqlite3")

    @contextmanager
    def _connect(self):
        with self._lock:
            db = self._temporary or sqlite3.connect(self.path, timeout=10)
            db.row_factory = sqlite3.Row
            try:
                with db:
                    yield db
            finally:
                if self._temporary is None:
                    db.close()

    @staticmethod
    def _message(row):
        value = dict(row)
        value["sources"] = json.loads(value.get("sources", "[]"))
        return value

    def add(self, role, message, sources=None, status="complete"):
        with self._connect() as db:
            cursor = db.execute("INSERT INTO messages(role,message,conversation_id,status,sources) VALUES(?,?,?,?,?)",
                                (role, message, self.conversation_id, status, json.dumps(sources or [], ensure_ascii=False)))
            db.execute("UPDATE conversations SET updated_at=CURRENT_TIMESTAMP WHERE id=?", (self.conversation_id,))
            return cursor.lastrowid

    def recent(self, limit=12, complete_only=False):
        return list(reversed(self.page(limit=limit, complete_only=complete_only)))

    def page(self, limit=200, before=None, query="", all_conversations=False, complete_only=False):
        clauses = ["1=1"]
        values = []
        if not all_conversations:
            clauses.append("conversation_id=?")
            values.append(self.conversation_id)
        if before is not None:
            clauses.append("id<?")
            values.append(before)
        if query:
            clauses.append("instr(lower(message),lower(?))>0")
            values.append(query)
        if complete_only:
            clauses.append("status='complete'")
        with self._connect() as db:
            return [self._message(row) for row in db.execute(
                "SELECT * FROM messages WHERE " + " AND ".join(clauses) + " ORDER BY id DESC LIMIT ?", (*values, limit))]

    @property
    def history(self):
        with self._connect() as db:
            return [self._message(row) for row in db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (self.conversation_id,))]

    def conversations(self):
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT c.*, (SELECT count(*) FROM messages m WHERE m.conversation_id=c.id) AS messages FROM conversations c ORDER BY updated_at DESC,c.rowid DESC")]

    def new_conversation(self, title="New conversation"):
        identity = uuid.uuid4().hex
        with self._connect() as db:
            db.execute("INSERT INTO conversations(id,title) VALUES(?,?)", (identity, title.strip()[:120] or "New conversation"))
        self.conversation_id = identity
        self.select_conversation(identity)
        return identity

    def select_conversation(self, identity):
        with self._connect() as db:
            if not db.execute("SELECT 1 FROM conversations WHERE id=?", (identity,)).fetchone():
                raise ValueError("That conversation no longer exists.")
        self.conversation_id = identity
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO preferences VALUES('active_conversation',?)", (identity,))

    def rename_conversation(self, title):
        if not title.strip():
            raise ValueError("Give the conversation a name.")
        with self._connect() as db:
            db.execute("UPDATE conversations SET title=? WHERE id=?", (title.strip()[:120], self.conversation_id))

    def delete_conversation(self):
        with self._connect() as db:
            for table in ("messages", "pins"):
                db.execute(f"DELETE FROM {table} WHERE conversation_id=?", (self.conversation_id,))
            db.execute("DELETE FROM conversations WHERE id=?", (self.conversation_id,))
            row = db.execute("SELECT id FROM conversations ORDER BY updated_at DESC LIMIT 1").fetchone()
        if row:
            self.select_conversation(row[0])
        else:
            self.new_conversation()

    def pins(self):
        with self._connect() as db:
            return [dict(row) for row in db.execute("SELECT * FROM pins WHERE conversation_id=? ORDER BY id", (self.conversation_id,))]

    def pin(self, content, label="Decision"):
        if not content.strip():
            raise ValueError("Write something to remember.")
        if len(content) > 2000:
            raise ValueError("Keep each pinned item under 2,000 characters so it can fit into recall.")
        if label not in {"Fact", "Decision", "Idea"}:
            raise ValueError("Choose Fact, Decision or Idea.")
        with self._connect() as db:
            return db.execute("INSERT INTO pins(conversation_id,label,content) VALUES(?,?,?)", (self.conversation_id, label, content.strip())).lastrowid

    def unpin(self, identity):
        with self._connect() as db:
            db.execute("DELETE FROM pins WHERE id=? AND conversation_id=?", (identity, self.conversation_id))

    def summary(self):
        with self._connect() as db:
            return dict(db.execute("SELECT summary,summary_until FROM conversations WHERE id=?", (self.conversation_id,)).fetchone())

    def summarize(self, ai, cancel_event=None, force=False):
        current = self.summary()
        recent = self.recent(12, complete_only=True)
        cutoff = recent[0]["id"] if recent else 0
        with self._connect() as db:
            rows = db.execute("SELECT * FROM messages WHERE conversation_id=? AND id>? AND id<? AND status='complete' ORDER BY id LIMIT 30",
                              (self.conversation_id, current["summary_until"], cutoff)).fetchall()
        if not rows or (len(rows) < 12 and not force):
            return False
        messages = []
        budget = min(12000, int(getattr(ai, "context_tokens", 8192)))
        for row in rows:
            if budget <= 0:
                break
            text = row["message"][:min(3000, budget)]
            messages.append({"id": row["id"], "role": row["role"], "message": text})
            budget -= len(text)
        previous = current["summary"][:min(3000, int(getattr(ai, "context_tokens", 8192)) // 3)]
        summary = ai.summarize_conversation(previous, messages, cancel_event)
        if cancel_event and cancel_event.is_set():
            return False
        if not isinstance(summary, str) or not summary.strip():
            return False
        with self._connect() as db:
            db.execute("UPDATE conversations SET summary=?,summary_until=? WHERE id=?",
                       (summary[:6000], messages[-1]["id"], self.conversation_id))
        return True

    def recall(self, question, budget=12000, expansions=(), semantic=None, cancel_event=None, all_conversations=False):
        recent = self.recent(12, complete_only=True)
        cutoff = recent[0]["id"] if recent else 0
        query_terms = set(terms(question))
        expanded = list(expansions)
        for item in recent[-4:]:
            if item["role"] == "user":
                expanded.append(item["message"][:500])
        candidates = []
        scope = "(m.id<? OR m.conversation_id<>?)" if all_conversations else "m.id<? AND m.conversation_id=?"
        scope_values = (cutoff, self.conversation_id)
        with self._connect() as db:
            search_words = list(dict.fromkeys([*query_terms, *terms(" ".join(expanded))]))[:64]
            if self.fts and search_words:
                expression = " OR ".join('"' + word.replace('"', '""') + '"' for word in search_words)
                candidates = [self._message(row) for row in db.execute(
                    "SELECT m.* FROM message_search JOIN messages m ON m.id=message_search.rowid WHERE message_search MATCH ? AND " + scope + " AND m.status='complete' ORDER BY rank LIMIT 120",
                    (expression, *scope_values))]
            elif not self.fts:
                candidates = [self._message(row) for row in db.execute("SELECT m.* FROM messages m WHERE " + scope + " AND m.status='complete'", scope_values)]
            if semantic:
                # Embedding retrieval covers old messages even when no keywords overlap.
                candidates = [self._message(row) for row in db.execute("SELECT m.* FROM messages m WHERE " + scope + " AND m.status='complete'", scope_values)]
        scores = Ranker([item["message"] for item in candidates]).scores(question, expanded)
        if semantic and candidates:
            similarities, _ = semantic.rank(question, [item["message"] for item in candidates], cancel_event)
            for number, similarity in similarities:
                if similarity > 0.35:
                    scores[number] += similarity * 3
        order = sorted(range(len(scores)), key=lambda number: (-scores[number], -candidates[number]["id"]))
        with self._connect() as db:
            old = {}
            for number in order[:8]:
                if scores[number] <= 0:
                    continue
                identity = candidates[number]["id"]
                conversation_id = candidates[number]["conversation_id"]
                neighbors = db.execute("SELECT * FROM messages WHERE conversation_id=? AND id<=? AND status='complete' ORDER BY id DESC LIMIT 2", (conversation_id, identity)).fetchall()
                neighbors += db.execute("SELECT * FROM messages WHERE conversation_id=? AND id>? AND (id<? OR conversation_id<>?) AND status='complete' ORDER BY id LIMIT 1", (conversation_id, identity, cutoff, self.conversation_id)).fetchall()
                for row in neighbors:
                    old.setdefault(row["id"], self._message(row))
            titles = {row["id"]: row["title"] for row in db.execute("SELECT id,title FROM conversations")}
        chosen = {}
        recent_budget = budget // 2 if old else budget
        for item in reversed(recent):
            if recent_budget <= 0:
                break
            text = item["message"][:min(1800, recent_budget)]
            chosen[item["id"]] = dict(item, message=text)
            budget -= len(text)
            recent_budget -= len(text)
        for identity, item in old.items():
            if budget <= 0:
                break
            text = item["message"]
            # Find the relevant part of a long exchange, rather than always taking its opening.
            location = min((text.casefold().find(word) for word in query_terms if word in text.casefold()), default=0)
            start = max(0, location - 400)
            excerpt = text[start:start + min(2800, budget)]
            chosen[identity] = dict(item, message=excerpt)
            budget -= len(excerpt)
        return [dict(chosen[identity], conversation_title=titles.get(chosen[identity]["conversation_id"], "")) for identity in sorted(chosen)]

    def context(self, question, budget=9000, expansions=(), semantic=None, cancel_event=None, all_conversations=False):
        pinned = []
        pins = self.pins()
        for item in reversed(pins):
            line = f"User-pinned {item['label']}: {item['content']}"
            if sum(map(len, pinned)) + len(line) <= budget // 2:
                pinned.append(line)
        summary = self.summary()["summary"][:budget // 4]
        history_budget = max(0, budget - sum(map(len, pinned)) - len(summary))
        history = self.recall(question, history_budget, expansions, semantic, cancel_event, all_conversations)
        return {"pins": list(reversed(pinned)), "summary": summary, "history": history,
                "omitted_pins": len(pins) - len(pinned)}

    def export(self, destination, cancel_event=None):
        destination = Path(destination)
        conversation = next(item for item in self.conversations() if item["id"] == self.conversation_id)
        pins = self.pins()
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent, prefix=".nemo-export-", suffix=".tmp", delete=False) as file:
                temporary = file.name
                as_json = destination.suffix.casefold() == ".json"
                if as_json:
                    file.write('{"conversation":')
                    json.dump(conversation, file, ensure_ascii=False)
                    file.write(',"pins":')
                    json.dump(pins, file, ensure_ascii=False)
                    file.write(',"messages":[')
                else:
                    file.write(f"# {conversation['title']}\n\nTimestamps are UTC.\n\n")
                    for item in pins:
                        file.write(f"Pinned {item['label']}: {item['content']}\n\n")
                first = True
                with self._connect() as db:
                    for row in db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (self.conversation_id,)):
                        if cancel_event and cancel_event.is_set():
                            raise RuntimeError("Export stopped. The previous file was kept.")
                        item = self._message(row)
                        if as_json:
                            if not first:
                                file.write(",")
                            json.dump(item, file, ensure_ascii=False)
                        else:
                            file.write(f"## {item['role'].capitalize()} - {item['created_at']} ({item['status']})\n\n{item['message']}\n\n")
                            for source in item["sources"]:
                                if isinstance(source, dict):
                                    file.write(f"[{source['id']}] {source['path']} (lines {source['start_line']}-{source['end_line']})\n\n{source['text']}\n\n")
                                else:
                                    file.write(f"Source: {source}\n\n")
                        first = False
                if as_json:
                    file.write("]}")
                file.flush()
                os.fsync(file.fileno())
            if cancel_event and cancel_event.is_set():
                raise RuntimeError("Export stopped. The previous file was kept.")
            os.replace(temporary, destination)
        finally:
            if temporary and Path(temporary).exists():
                Path(temporary).unlink()

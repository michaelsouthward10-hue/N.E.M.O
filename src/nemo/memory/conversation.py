"""Durable, vault-specific conversation archive with full-history retrieval."""
import hashlib
import heapq
import re
import sqlite3
from pathlib import Path


class ConversationMemory:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        # Keep no open connections across GUI worker threads.
        self._temporary = sqlite3.connect(":memory:", check_same_thread=False) if not self.path else None
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, role TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)")

    @classmethod
    def for_vault(cls, vault_path):
        if not vault_path:
            return cls()
        from nemo.core.paths import DATA_DIR
        identity = str(Path(vault_path).resolve()).casefold()
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return cls(DATA_DIR / "conversations" / f"{key}.sqlite3")

    def _connect(self):
        from contextlib import contextmanager

        @contextmanager
        def connection():
            db = self._temporary or sqlite3.connect(self.path)
            try:
                with db:
                    yield db
            finally:
                if self._temporary is None:
                    db.close()
        return connection()

    def add(self, role, message):
        with self._connect() as db:
            db.execute("INSERT INTO messages (role, message) VALUES (?, ?)", (role, message))

    def recent(self, limit=12):
        with self._connect() as db:
            rows = db.execute("SELECT role, message FROM messages ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [{"role": role, "message": message} for role, message in reversed(rows)]

    @property
    def history(self):
        with self._connect() as db:
            return [{"role": role, "message": message} for role, message in db.execute("SELECT role, message FROM messages ORDER BY id")]

    @staticmethod
    def _terms(text):
        stop = {"the", "and", "that", "this", "with", "what", "have", "about", "were", "was", "you", "our", "for", "from", "how", "did", "can", "does", "previously", "discuss", "discussed"}
        return {word for word in re.findall(r"\w+", text.lower()) if len(word) > 2 and word not in stop}

    def recall(self, question, budget=24000):
        """Search every stored message; combine older matches and recent turns.

        Storage has no message cap. Only the context sent to the model is bounded.
        Neighboring turns keep answers attached to the questions they answered.
        """
        with self._connect() as db:
            recent = db.execute("SELECT id, role, message FROM messages ORDER BY id DESC LIMIT 12").fetchall()
            primary_terms = self._terms(question)
            terms = set(primary_terms)
            for _, role, message in recent[:4]:
                if role == "user":
                    terms |= self._terms(message)
            cutoff = min((row[0] for row in recent), default=0)
            def scored():
                for row in db.execute("SELECT id, role, message FROM messages WHERE id < ?", (cutoff,)):
                    words = self._terms(row[2])
                    score = 10 * len(primary_terms & words) + len(terms & words)
                    if score:
                        yield (score, row[0])
            matches = heapq.nlargest(8, scored())
            selected = {row[0]: row for row in recent}
            for _, message_id in matches:
                for row in db.execute("SELECT id, role, message FROM messages WHERE id BETWEEN ? AND ?", (message_id - 1, message_id + 1)):
                    selected[row[0]] = row
        # Reserve room for recent turns before allocating older recollections.
        chosen = {}
        recent_budget = budget // 2 if matches else budget
        for message_id in [row[0] for row in recent] + [row_id for row_id in sorted(selected) if row_id < cutoff]:
            _, role, message = selected[message_id]
            if budget <= 0:
                break
            allowance = min(2000, recent_budget) if message_id >= cutoff else min(4000, budget)
            if allowance <= 0:
                continue
            excerpt = message[:allowance]
            if len(excerpt) < len(message):
                excerpt += " [excerpt]"
            chosen[message_id] = {"role": role, "message": excerpt}
            budget -= len(excerpt)
            if message_id >= cutoff:
                recent_budget -= len(excerpt)
        return [chosen[key] for key in sorted(chosen)]

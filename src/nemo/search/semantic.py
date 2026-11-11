"""Optional, local embedding cache. No model is downloaded automatically."""
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from nemo.ai.ollama_client import GenerationCancelled


class SemanticSearch:
    def __init__(self, path, ai):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.ai = ai
        self.namespace = ai.endpoint + "/" + ai.embedding_model
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS vectors (namespace TEXT, digest TEXT, vector TEXT, PRIMARY KEY(namespace, digest))")

    @staticmethod
    def cosine(first, second):
        if len(first) != len(second):
            return 0
        norm = math.sqrt(sum(x * x for x in first) * sum(x * x for x in second))
        return sum(x * y for x, y in zip(first, second)) / norm if norm else 0

    def rank(self, query, texts, cancel_event=None):
        try:
            digests = [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts]
            with sqlite3.connect(self.path) as db:
                vectors = {}
                unique = list(dict.fromkeys(digests))
                for start in range(0, len(unique), 400):
                    batch = unique[start:start + 400]
                    placeholders = ",".join("?" for _ in batch)
                    vectors.update({digest: json.loads(vector) for digest, vector in db.execute(
                        f"SELECT digest,vector FROM vectors WHERE namespace=? AND digest IN ({placeholders})", (self.namespace, *batch))})
                pending = list(dict.fromkeys(digest for digest in digests if digest not in vectors))
                by_digest = dict(zip(digests, texts))
                for start in range(0, len(pending), 16):
                    if cancel_event and cancel_event.is_set():
                        raise GenerationCancelled()
                    batch = pending[start:start + 16]
                    embedded = self.ai.embed([by_digest[digest] for digest in batch], cancel_event)
                    for digest, vector in zip(batch, embedded):
                        if not vector or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
                            raise ValueError("Invalid embedding vector")
                        vectors[digest] = vector
                        db.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)",
                                   (self.namespace, digest, json.dumps(vector)))
                    db.commit()
            query_vector = self.ai.embed([query], cancel_event)[0]
            return [(number, self.cosine(query_vector, vectors[digest])) for number, digest in enumerate(digests)], ""
        except GenerationCancelled:
            raise
        except Exception:
            return [], "Embedding search is unavailable. Word-based search and question expansion were used. Check the embedding model in AI settings."

    def clear(self):
        with sqlite3.connect(self.path) as db:
            db.execute("DELETE FROM vectors")

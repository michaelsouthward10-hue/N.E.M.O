from collections import Counter
from pathlib import Path

from nemo.core.paths import DATA_DIR
from nemo.core.storage import index_path, load_vault_index
from nemo.indexing.links import LinkResolver
from nemo.search.ranking import Ranker, passages, terms


class SearchEngine:
    def __init__(self, vault_path=None):
        self._unbound = vault_path == ""
        self.vault_path = Path(vault_path) if vault_path else None
        self.index_path = index_path(vault_path, DATA_DIR) if vault_path else DATA_DIR / "index.json"
        self.warning = ""
        self.index = self.load_index()
        self._keys = list(self.index)
        self._ranker = Ranker([self._search_text(self.index[key]) for key in self._keys])
        self._passages = None
        self._resolver = LinkResolver(self.index)
        self._neighbors = {key: set() for key in self.index}
        for key, note in self.index.items():
            for link in note.get("links", []):
                target = self._resolver.resolve(link, note.get("path", key))
                if target and target != key:
                    self._neighbors[key].add(target)
                    self._neighbors[target].add(key)

    def load_index(self):
        if self._unbound:
            return {}
        try:
            return load_vault_index(self.index_path, self.vault_path)
        except (ValueError, OSError) as error:
            self.warning = f"Could not load this vault's index: {error} Click Reindex to rebuild it."
            return {}

    @staticmethod
    def _search_text(note):
        return " ".join([note.get("title", "")] * 4 + [note.get("path", "")] * 2 + note.get("aliases", []) * 3
                        + note.get("tags", []) * 2 + [note.get("text", "")])

    def search_by_title(self, title):
        found = self._resolver.resolve(title)
        if found is not None:
            return self.index[found]
        query = str(title).casefold()
        matches = [note for note in self.index.values() if query in note.get("title", "").casefold()]
        return matches[0] if len(matches) == 1 else None

    def search_by_tag(self, tag):
        return [note for note in self.index.values() if tag.casefold() in
                [item.casefold() for item in note.get("tags", [])]]

    def search_by_link(self, link):
        return [note for note in self.index.values() if link.casefold() in
                [item.casefold() for item in note.get("links", [])]]

    def search_by_text(self, query, limit=12, expansions=()):
        if not terms(query) and not expansions:
            return []
        scores = self._ranker.scores(query, expansions)
        return [self.index[self._keys[number]] for number in
                sorted(range(len(scores)), key=lambda number: (-scores[number], self._keys[number]))[:limit]
                if scores[number] > 0]

    def score_note(self, note, query):
        return Ranker([self._search_text(note)]).scores(query)[0]

    def retrieve(self, query, expansions=(), limit=12, max_chars=14000, semantic=None, cancel_event=None):
        if self._passages is None:
            self._passages = [passage for key, note in self.index.items() for passage in passages(note, key)]
            self._passage_ranker = Ranker([" ".join(
                [passage["title"]] * 3 + [passage["path"]] * 2
                + self.index[passage["note_key"]].get("aliases", []) * 2
                + self.index[passage["note_key"]].get("tags", []) + [passage["text"]]) for passage in self._passages])
        scores = self._passage_ranker.scores(query, expansions)
        semantic_warning = ""
        if semantic and self._passages:
            similarities, semantic_warning = semantic.rank(query, [p["text"] for p in self._passages], cancel_event)
            for number, similarity in similarities:
                if similarity > 0.35:
                    scores[number] += similarity * 3
        ranked = sorted(range(len(scores)), key=lambda number: (-scores[number], number))
        roots = []
        for number in ranked:
            key = self._passages[number]["note_key"]
            if scores[number] > 0 and key not in roots:
                roots.append(key)
            if len(roots) == 8:
                break
        linked = set()
        for key in roots[:4]:
            linked.update(self._neighbors[key])
        # Include one passage from a relevant linked note even if it uses different terminology.
        extra = []
        for key in sorted(linked - set(roots))[:8]:
            candidates = [number for number, passage in enumerate(self._passages) if passage["note_key"] == key]
            if candidates:
                best = max(candidates, key=lambda number: scores[number])
                scores[best] = max(scores[best], 0.05)
                extra.append(best)
        candidates = [number for number in ranked if scores[number] > 0]
        # Reserve some space for link exploration without displacing the best direct matches.
        candidates = candidates[:max(0, limit - min(3, len(extra)))] + extra[:3] + candidates
        chosen = []
        seen = set()
        per_note = Counter()
        for number in candidates:
            if number in seen or len(chosen) >= limit or max_chars <= 0:
                continue
            passage = self._passages[number]
            key = passage["note_key"]
            if per_note[key] >= 2:
                continue
            item = dict(passage)
            item["text"] = item["text"][:max_chars]
            item["id"] = f"S{len(chosen) + 1}"
            item["via_link"] = number in extra
            chosen.append(item)
            seen.add(number)
            per_note[key] += 1
            max_chars -= len(item["text"])
        self.retrieval_warning = semantic_warning
        return chosen

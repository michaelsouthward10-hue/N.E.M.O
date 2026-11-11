"""Small, dependency-free BM25 ranking for notes and saved conversations."""
from collections import Counter
import math
import re

STOP = set("a an the and or of to in on at by for with from is are was were be been it its he she they them him her his their this that those these i we you our your me my what which who why how when where do does did can could would should tell about please as have has had not".split())


def terms(text):
    words = re.findall(r"[^\W_]+", str(text).casefold(), re.UNICODE)
    result = []
    for word in words:
        if word in STOP or len(word) < 2:
            continue
        if len(word) > 5 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us")):
            word = word[:-1]
        result.append(word)
    return result


class Ranker:
    def __init__(self, texts):
        self.documents = [Counter(terms(text)) for text in texts]
        self.lengths = [sum(document.values()) for document in self.documents]
        self.average = sum(self.lengths) / max(1, len(self.lengths)) or 1
        self.frequency = Counter()
        for document in self.documents:
            self.frequency.update(document.keys())

    def scores(self, query, expansions=()):
        weights = {word: 1.0 for word in terms(query)}
        for expansion in expansions:
            for word in terms(expansion):
                weights.setdefault(word, 0.45)
        scores = []
        count = len(self.documents)
        for document, length in zip(self.documents, self.lengths):
            score = 0.0
            for word, weight in weights.items():
                frequency = document.get(word, 0)
                if not frequency:
                    continue
                inverse = math.log(1 + (count - self.frequency[word] + 0.5) / (self.frequency[word] + 0.5))
                score += weight * inverse * frequency * 2.2 / (frequency + 1.2 * (0.25 + 0.75 * length / self.average))
            scores.append(score)
        return scores


def passages(note, key, max_chars=1600):
    lines = note.get("text", "").splitlines()
    result = []
    start = 0
    while start < len(lines):
        end = start
        size = 0
        while end < len(lines) and (size + len(lines[end]) < max_chars or end == start):
            size += len(lines[end]) + 1
            end += 1
        text = "\n".join(lines[start:end])
        for offset in range(0, max(1, len(text)), max_chars):
            excerpt = text[offset:offset + max_chars]
            if excerpt.strip():
                result.append({"path": note.get("path", key), "title": note.get("title", key),
                               "start_line": start + 1, "end_line": end, "text": excerpt,
                               "note_key": key, "kind": "vault"})
        start = max(start + 1, end - 1) if end < len(lines) else end
    return result

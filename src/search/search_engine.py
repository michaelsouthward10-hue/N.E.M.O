import json
from pathlib import Path


class SearchEngine:

    def __init__(self):
        self.index_path = Path("data/index.json")
        self.index = self.load_index()

    def load_index(self):
        with open(self.index_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def search_by_title(self, title):
        return self.index.get(title)

    def search_by_tag(self, tag):

        results = []

        for note in self.index.values():

            if tag.lower() in [
                t.lower() for t in note.get("tags", [])
            ]:

                results.append(note)

        return results

    def search_by_link(self, link):

        results = []

        for note in self.index.values():

            if link.lower() in [
                l.lower() for l in note.get("links", [])
            ]:

                results.append(note)

        return results
    
    def search_by_text(self, query):

        matches = []

        for note in self.index.values():

            score = self.score_note(note, query)

            if score > 0:
                matches.append((score, note))

        matches.sort(reverse=True, key=lambda x: x[0])

        print("\nTop Matches")

        for score, note in matches[:5]:
            print(score, "-", note["title"])

        return [note for score, note in matches[:5]]
    
    def score_note(self, note, query):

        score = 0

        query = query.lower()
        if query in note.get("title", "").lower():
            score += 10

        if query in note.get("summary", "").lower():
            score += 5

        if query in note.get("text", "").lower():
            score += 2

        for tag in note.get("tags", []):
            if query == tag.lower():
                score += 8

        return score
from nemo.ai.chat import NemoChat


class FakeAI:
    def __init__(self):
        self.prompts = []

    def answer(self, prompt):
        self.prompts.append(prompt)
        return "Oracle response."


class FakeRouter:
    def __init__(self):
        self.questions = []

    def route(self, _question):
        return "general"

    def handle(self, question):
        self.questions.append(question)
        return {"result": ["Athena", "Odysseus"]}


class FakeSearch:
    def __init__(self, notes=None):
        self.notes = notes or []
        self.queries = []

    def search_by_text(self, query):
        self.queries.append(query)
        return self.notes


def make_chat(notes=None):
    ai = FakeAI()
    router = FakeRouter()
    chat = NemoChat(ai, router=router)
    chat.search = FakeSearch(notes)
    return chat, ai, router


def test_find_connections_uses_local_relationship_router():
    chat, ai, router = make_chat()

    result = chat.ask("Athena and Odysseus", mode="Find connections")

    assert result == {"answer": "Athena → Odysseus", "sources": ["Athena", "Odysseus"]}
    assert router.questions == ["How are Athena and Odysseus connected?"]
    assert ai.prompts == []


def test_summarize_topic_uses_matching_notes_as_context():
    note = {"title": "Athena", "summary": "Goddess of wisdom", "text": "Athena is a goddess."}
    chat, ai, _router = make_chat([note])

    result = chat.ask("Athena", mode="Summarize topic")

    assert result == {"answer": "Oracle response.", "sources": ["Athena"]}
    assert chat.search.queries == ["Athena"]
    assert "using only the supplied Obsidian notes" in ai.prompts[0]
    assert "Athena is a goddess." in ai.prompts[0]


def test_develop_idea_allows_an_idea_without_matching_notes():
    chat, ai, _router = make_chat()

    result = chat.ask("A city built on the back of a whale", mode="Develop idea")

    assert result == {"answer": "Oracle response.", "sources": []}
    assert "without claiming vault support" in ai.prompts[0]


def test_summarize_topic_without_notes_does_not_call_ai():
    chat, ai, _router = make_chat()

    result = chat.ask("Atlantis", mode="Summarize topic")

    assert "couldn't find any notes" in result["answer"]
    assert result["sources"] == []
    assert ai.prompts == []

from nemo.ai.chat import NemoChat


class FakeAI:
    def __init__(self):
        self.prompts = []

    def answer(self, prompt):
        self.prompts.append(prompt)
        return "An answer grounded in the vault."


class FakeRouter:
    def __init__(self, result=None):
        self.result = result or {"type": "relationship", "result": ["Michael", "Lucifer"]}
        self.handled = []

    def route(self, question):
        return "relationship" if "connected" in question.lower() else "general"

    def handle(self, question):
        self.handled.append(question)
        return self.result


class FakeSearch:
    def __init__(self):
        self.queries = []

    def search_by_text(self, query):
        self.queries.append(query)
        return [{"title": "Michael", "summary": "An archangel.", "text": "Michael is an archangel."}]


def make_chat(router=None, vault_path=None):
    ai = FakeAI()
    chat = NemoChat(ai, router=router or FakeRouter(), vault_path=vault_path)
    chat.search = FakeSearch()
    return chat, ai


def test_relationship_question_uses_graph_without_calling_ai():
    router = FakeRouter()
    chat, ai = make_chat(router)

    result = chat.ask("How is Michael connected to Lucifer?")

    assert result == {"answer": "Michael → Lucifer", "sources": ["Michael", "Lucifer"]}
    assert router.handled == ["How is Michael connected to Lucifer?"]
    assert ai.prompts == []


def test_general_question_keeps_search_and_ai_flow():
    chat, ai = make_chat()

    result = chat.ask("Who is Michael?")

    assert result["answer"] == "An answer grounded in the vault."
    assert result["sources"] == ["Michael"]
    assert chat.search.queries == ["Michael"]
    assert len(ai.prompts) == 1


def test_note_request_writes_markdown_in_vault_without_overwriting(tmp_path):
    chat, ai = make_chat(vault_path=tmp_path)

    result = chat.ask("new note: Michael's abilities")

    note = tmp_path / "Michael's abilities.md"
    assert result["answer"] == "Created the note 'Michael's abilities' in your Obsidian vault."
    assert note.read_text(encoding="utf-8") == "# Michael's abilities\n\nAn answer grounded in the vault.\n"
    assert len(ai.prompts) == 1

    repeated = chat.ask("new note: Michael's abilities")
    assert "already exists" in repeated["answer"]
    assert len(ai.prompts) == 1


def test_save_note_writes_user_content_without_calling_ai(tmp_path):
    chat, ai = make_chat(vault_path=tmp_path)
    body = "A note written by hand.\n\nIt keeps [[Obsidian]] Markdown intact."

    result = chat.save_note("My Note", body)

    note = tmp_path / "My Note.md"
    assert result["answer"] == "Created the note 'My Note' in your Obsidian vault."
    assert result["sources"] == [str(note)]
    assert note.read_text(encoding="utf-8") == f"# My Note\n\n{body}\n"
    assert ai.prompts == []


def test_save_note_does_not_overwrite_an_existing_note(tmp_path):
    chat, ai = make_chat(vault_path=tmp_path)
    note = tmp_path / "My Note.md"
    note.write_text("Existing contents", encoding="utf-8")

    result = chat.save_note("My Note", "New contents")

    assert "already exists" in result["answer"]
    assert note.read_text(encoding="utf-8") == "Existing contents"
    assert ai.prompts == []

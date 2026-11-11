import threading

from nemo.ai.chat import NemoChat
from nemo.ai.prompt_builder import PromptBuilder
from nemo.core.scanner import VaultScanner
from nemo.search.search_engine import SearchEngine
from test_vault_storage import write_note


def test_ranked_passages_find_natural_questions_and_exact_lines(tmp_path):
    vault = tmp_path / "vault"
    write_note(vault, "Michael.md", "---\naliases: [The Protector]\ntags: [archangels]\n---\n# Michael\nHe opposed Lucifer because of his loyalty to the creator.")
    write_note(vault, "Unrelated.md", "A recipe for soup.")
    VaultScanner(vault).scan()
    engine = SearchEngine(vault)
    assert engine.search_by_title("The Protector")["title"] == "Michael"
    result = engine.retrieve("Why did Michael oppose Lucifer?")
    assert result[0]["path"] == "Michael.md"
    original_lines = (vault / "Michael.md").read_text().splitlines()
    for item in result:
        assert item["text"] in "\n".join(original_lines[item["start_line"] - 1:item["end_line"]])


def test_retrieval_uses_more_than_three_notes_and_follows_links(tmp_path):
    vault = tmp_path / "vault"
    for number in range(6):
        write_note(vault, f"War{number}.md", f"The celestial war account {number}. [[Aftermath]]")
    write_note(vault, "Aftermath.md", "The survivors rebuilt their home.")
    VaultScanner(vault).scan()
    result = SearchEngine(vault).retrieve("celestial war")
    assert len({item["path"] for item in result}) >= 6
    assert any(item["path"] == "Aftermath.md" and item["via_link"] for item in result)


def test_model_rephrasing_resolves_followup_and_semantic_terms(tmp_path):
    vault = tmp_path / "vault"
    write_note(vault, "Conflict.md", "Michael's allegiance to the creator led to rebellion against Lucifer.")
    VaultScanner(vault).scan()
    class AI:
        context_tokens = 8192
        def plan_question(self, question, discussion, cancel_event=None):
            self.discussion = discussion
            return {"resolved_question": "Why did Michael turn against Lucifer?", "search_terms": ["allegiance creator rebellion"], "clarification": ""}
        def answer(self, prompt, on_token=None, cancel_event=None):
            self.prompt = prompt
            if on_token:
                on_token("Because of his allegiance [S1].")
            return "Because of his allegiance [S1]."
    ai = AI()
    chat = NemoChat(ai, vault_path=vault)
    chat.memory.add("user", "Tell me about Michael")
    chat.memory.add("assistant", "We are discussing Michael.")
    result = chat.ask("Why did he turn against him?")
    assert "Michael" in str(ai.discussion)
    assert "allegiance" in ai.prompt
    assert result["cited"] == ["S1"]
    assert result["evidence"][0]["cited"]


def test_missing_and_invented_citations_are_flagged():
    evidence = [{"id": "S1"}]
    answer, cited, warnings = PromptBuilder.check_citations("A claim [S99].", evidence)
    assert "[source unavailable]" in answer
    assert not cited and len(warnings) == 2


def test_ambiguous_followup_asks_before_generating(tmp_path):
    from test_chat_routing import FakeAI, FakeRouter
    ai = FakeAI()
    chat = NemoChat(ai, router=FakeRouter(), vault_path=tmp_path)
    chat.memory.add("assistant", "Two characters", sources=["Michael", "Lucifer"])
    result = chat.ask("Why did he do that?")
    assert "Which character" in result["answer"]
    assert not ai.prompts


def test_general_chat_does_not_load_the_legacy_shared_index(sample_index):
    from test_chat_routing import FakeAI
    chat = NemoChat(FakeAI(), vault_path="")
    assert not chat.search.index

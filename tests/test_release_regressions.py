import threading

from nemo.ai.chat import NemoChat
from nemo.ai.ollama_client import GenerationCancelled
from nemo.memory.conversation import ConversationMemory
from nemo.services.router import QuestionRouter
from test_chat_routing import FakeAI
from nemo.ai.prompt_builder import PromptBuilder


def test_asking_for_a_comparison_is_not_replaced_by_a_graph_path():
    assert QuestionRouter().route("What are the differences between Michael and Lucifer?") == "general"


def test_cancel_during_search_planning_does_not_show_internal_json():
    class AI(FakeAI):
        def plan_question(self, *args):
            raise GenerationCancelled('{"resolved_question":"internal search text"')
    result = NemoChat(AI()).ask("Why did he do that?", cancel_event=threading.Event())
    assert result["stopped"] and result["answer"] == "[Stopped]"


def test_cross_conversation_recall_is_explicit_and_stays_within_one_vault(tmp_path):
    first = ConversationMemory.for_vault(tmp_path / "first")
    first.add("user", "Veloria is the city we chose")
    first.new_conversation("Another story")
    assert not first.recall("Veloria")
    recalled = first.recall("Veloria", all_conversations=True)
    assert any("Veloria" in item["message"] for item in recalled)
    assert recalled[0]["conversation_title"] == "Main conversation"
    assert not ConversationMemory.for_vault(tmp_path / "second").recall("Veloria", all_conversations=True)


def test_long_pin_is_used_and_overflow_is_reported():
    memory = ConversationMemory()
    memory.pin("A" * 2000, "Fact")
    context = memory.context("facts", budget=6000)
    assert "A" * 2000 in context["pins"][0]
    for _ in range(5):
        memory.pin("B" * 2000, "Decision")
    assert memory.context("facts", budget=6000)["omitted_pins"] > 0


def test_combined_citations_are_normalized_and_checked():
    answer, cited, warnings = PromptBuilder.check_citations("Evidence [S1, S2].", [{"id": "S1"}, {"id": "S2"}])
    assert answer == "Evidence [S1] [S2]."
    assert cited == ["S1", "S2"] and not warnings


def test_canceled_export_preserves_existing_file(tmp_path):
    import pytest
    memory = ConversationMemory()
    memory.add("user", "Keep this message")
    path = tmp_path / "export.json"
    path.write_text("Previous export")
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(RuntimeError, match="Export stopped"):
        memory.export(path, cancel)
    assert path.read_text() == "Previous export"

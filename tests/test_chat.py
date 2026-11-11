import threading

from nemo.ai.chat import NemoChat
from nemo.ai.ollama_client import GenerationCancelled
from test_chat_routing import FakeAI, FakeRouter, FakeSearch


def test_stopped_answer_is_saved_as_incomplete():
    class StoppedAI(FakeAI):
        def answer(self, prompt):
            raise GenerationCancelled("Partial reply")
    chat = NemoChat(StoppedAI(), router=FakeRouter())
    chat.search = FakeSearch()
    result = chat.ask("Who is Michael?", cancel_event=threading.Event())
    assert result["stopped"]
    assert "Partial reply" in result["answer"]
    assert chat.memory.recent(1)[0]["status"] == "stopped"
    assert all(item["message"] != result["answer"] for item in chat.memory.recall("Michael"))

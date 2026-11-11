from nemo.memory.conversation import ConversationMemory
from nemo.ai.chat import NemoChat
from test_chat_routing import FakeAI, FakeRouter, FakeSearch


def test_log_survives_restart_without_truncating_messages(tmp_path):
    path = tmp_path / "chat.sqlite3"
    memory = ConversationMemory(path)
    original = "long message " * 3000
    memory.add("user", original)
    memory.add("assistant", "A saved response")
    restored = ConversationMemory(path)
    assert restored.history[0]["message"] == original
    assert restored.recent(1)[0]["message"] == "A saved response"


def test_recall_searches_old_turns_and_includes_adjacent_answer(tmp_path):
    memory = ConversationMemory(tmp_path / "chat.sqlite3")
    memory.add("user", "Let us call the hidden city Veloria")
    memory.add("assistant", "Its gates open only at dawn")
    for number in range(100):
        memory.add("user", f"Unrelated topic {number}")
        memory.add("assistant", "A different discussion")
    recalled = memory.recall("What did we decide about Veloria?")
    assert any("gates open" in item["message"] for item in recalled)
    assert len(memory.history) == 202


def test_long_recent_messages_do_not_hide_older_matches():
    memory = ConversationMemory()
    memory.add("user", "Veloria has silver gates")
    for _ in range(15):
        memory.add("assistant", "other " * 5000)
    recalled = memory.recall("Veloria")
    assert any("silver gates" in item["message"] for item in recalled)
    assert sum(len(item["message"]) for item in recalled) <= 24100


def test_vault_logs_are_isolated_and_reopened(tmp_path, monkeypatch):
    from nemo.core import paths
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    first = ConversationMemory.for_vault(tmp_path / "first")
    first.add("user", "Secret from first vault")
    assert ConversationMemory.for_vault(tmp_path / "second").history == []
    assert ConversationMemory.for_vault(tmp_path / "first").history == first.history


def test_chat_reuses_old_discussion_in_model_prompt(tmp_path, monkeypatch):
    from nemo.core import paths
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    vault = tmp_path / "vault"
    chat = NemoChat(FakeAI(), router=FakeRouter(), vault_path=vault)
    chat.memory.add("user", "Veloria was our proposed city name")
    chat.memory.add("assistant", "We suggested silver gates")
    for _ in range(20):
        chat.memory.add("user", "Unrelated topic")
    ai = FakeAI()
    restored = NemoChat(ai, router=FakeRouter(), vault_path=vault)
    restored.search = FakeSearch()
    restored.ask("Tell me our ideas for Veloria")
    assert "silver gates" in ai.prompts[0]
    assert restored.memory.recent(1)[0]["role"] == "assistant"
    restored.set_vault(tmp_path / "another-vault")
    assert restored.memory.history == []

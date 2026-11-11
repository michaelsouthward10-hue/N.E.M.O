import json
import sqlite3

from nemo.memory.conversation import ConversationMemory


def test_migrates_version_108_log_without_losing_messages(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE messages(id INTEGER PRIMARY KEY,role TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        db.execute("INSERT INTO messages(role,message) VALUES('user','Remember the city Veloria')")
    memory = ConversationMemory(path)
    assert memory.history[0]["message"] == "Remember the city Veloria"
    assert memory.history[0]["status"] == "complete"
    assert memory.conversations()[0]["messages"] == 1


def test_chats_pins_and_summaries_are_scoped_and_selection_survives_restart(tmp_path):
    path = tmp_path / "chat.sqlite3"
    memory = ConversationMemory(path)
    first = memory.conversation_id
    memory.add("user", "Veloria has silver gates")
    memory.pin("Keep the silver gates", "Decision")
    second = memory.new_conversation("Another story")
    assert not memory.history and not memory.pins()
    assert not memory.recall("Veloria")
    memory.pin("A new suggestion", "Idea")
    restored = ConversationMemory(path)
    assert restored.conversation_id == second
    restored.select_conversation(first)
    assert "silver gates" in restored.pins()[0]["content"]
    assert "silver gates" in str(restored.context("Veloria"))
    assert ConversationMemory(path).conversation_id == first


def test_old_decision_can_be_found_using_semantic_expansion():
    memory = ConversationMemory()
    memory.add("user", "The monarch abdicated the throne")
    memory.add("assistant", "The crown passed to his daughter")
    for _ in range(50):
        memory.add("user", "A completely different topic")
    recalled = memory.recall("Who took over after the king stepped down?", expansions=["monarch abdicated throne crown daughter"])
    assert any("daughter" in item["message"] for item in recalled)


def test_summaries_keep_raw_history_and_distinguish_ideas():
    memory = ConversationMemory()
    for number in range(40):
        memory.add("user" if number % 2 == 0 else "assistant", f"Turn {number} about a proposed city")
    class AI:
        def summarize_conversation(self, previous, messages, cancel_event=None):
            self.messages = messages
            return "User decision: city name Veloria. AI suggestion, not established lore: silver gates."
    ai = AI()
    assert memory.summarize(ai)
    assert len(memory.history) == 40
    assert "not established lore" in memory.summary()["summary"]
    assert memory.summary()["summary_until"] == ai.messages[-1]["id"]
    assert "User decision" in memory.context("city")["summary"]


def test_search_pagination_export_and_delete_only_current_chat(tmp_path):
    memory = ConversationMemory(tmp_path / "chat.sqlite3")
    original = memory.conversation_id
    for number in range(9):
        memory.add("user", f"Veloria decision {number}")
    first_page = memory.page(limit=4, query="Veloria")
    older = memory.page(limit=4, before=first_page[-1]["id"], query="Veloria")
    assert not {item["id"] for item in first_page} & {item["id"] for item in older}
    other = memory.new_conversation("Other")
    memory.add("user", "A separate story")
    memory.pin("Keep this idea", "Idea")
    destination = tmp_path / "export.json"
    memory.export(destination)
    exported = json.loads(destination.read_text(encoding="utf-8"))
    assert len(exported["messages"]) == 1 and exported["pins"][0]["label"] == "Idea"
    assert len(memory.page(all_conversations=True, query="Veloria")) == 9
    memory.delete_conversation()
    assert memory.conversation_id == original
    assert len(memory.history) == 9
    assert all(item["id"] != other for item in memory.conversations())
    assert len(ConversationMemory(memory.path).conversations()) == 1


def test_failed_and_stopped_messages_are_not_recalled_as_facts():
    memory = ConversationMemory()
    memory.add("assistant", "Invented lore", status="failed")
    memory.add("assistant", "An unfinished claim", status="stopped")
    assert not memory.recall("lore claim")
    assert len(memory.history) == 2

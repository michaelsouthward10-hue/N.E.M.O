from core.config import load_settings
from ai.ollama_client import OllamaClient
from ai.chat import NemoChat

settings = load_settings()
search = SearchEngine()

ai = OllamaClient(
    settings["ai"]["endpoint"],
    settings["ai"]["model"]
)

chat = NemoChat(ai, search)

print(chat.ask("Who is Michael?"))
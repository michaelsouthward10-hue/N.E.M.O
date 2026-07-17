import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config import load_settings
from ai.ollama_client import OllamaClient
from ai.chat import NemoChat

settings = load_settings()

ai = OllamaClient(
    settings["ai"]["endpoint"],
    settings["ai"]["model"]
)

chat = NemoChat(ai)

print(chat.ask("Who is Michael?"))
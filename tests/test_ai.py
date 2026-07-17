import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nemo.core.config import load_settings
from nemo.ai.ollama_client import OllamaClient

settings = load_settings()

ai = OllamaClient(
    settings["ai"]["endpoint"],
    settings["ai"]["model"]
)

text = """
Bolt of Wicked Wrath

Depending on their affinity,
the demon can shoot a bolt
of channelled anger.
"""

result = ai.summarize(text)

print(result)
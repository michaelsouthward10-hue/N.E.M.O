from core.config import load_settings
from ai.summarizer import Summarizer

print("Loading settings...")

settings = load_settings()

print("Creating AI...")

ai = Summarizer(
    settings["ai"]["endpoint"],
    settings["ai"]["model"]
)

print("Sending request to Ollama...")

text = """
Bolt of Wicked Wrath

Depending on their affinity,
the demon can shoot a bolt
of channelled anger.
"""

result = ai.summarize(text)

print("Response received:")
print(result)
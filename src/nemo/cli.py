from nemo.core.config import load_settings
from nemo.ai.ollama_client import OllamaClient
from nemo.ai.chat import NemoChat
from nemo.search.search_engine import SearchEngine


settings = load_settings()

search = SearchEngine()

ai = OllamaClient(
    settings["ai"]["endpoint"],
    settings["ai"]["model"]
)

chat = NemoChat(ai)

from rich.console import Console
from rich.panel import Panel

console = Console()

console.print(
    Panel.fit(
        "[bold cyan]NEMO[/bold cyan]\n"
        "Narrative Engine for Mythological Organisation\n\n"
        "[green]Status:[/green] Online",
        title="Version 0.5"
    )
)

while True:

    command = input("> ").strip()

    if command.lower() == "exit":
        break

    if command.lower() == "help":
        ...
        continue

    if command.lower() == "status":
        ...
        continue


    result = chat.ask(command)

    print("TYPE:", type(result))
    print("VALUE:", result)

    console.print("\nNEMO:\n")
    console.print(result["answer"])

    console.print("\nSources:")

    for source in result["sources"]:
        console.print(f"- {source}")
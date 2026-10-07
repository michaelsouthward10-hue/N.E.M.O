from nemo.core.config import load_settings
from nemo.ai.ollama_client import OllamaClient
from nemo.ai.chat import NemoChat
from nemo.search.search_engine import SearchEngine
from nemo.services.router import QuestionRouter


settings = load_settings()

search = SearchEngine()

ai = OllamaClient(
    settings["ai"]["endpoint"],
    settings["ai"]["model"]
)

chat = NemoChat(ai, vault_path=settings["vault"]["path"])

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
        console.print("Ask a question about your vault, or use 'new note: <title>' to create a note.")
        console.print("Type 'reindex' after adding or editing notes in Obsidian, or 'exit' to quit.")
        continue

    if command.lower() == "reindex":
        from nemo.core.system import SystemManager

        SystemManager().scan_vault()
        chat.search = SearchEngine()
        chat.router = QuestionRouter()
        console.print("Vault index refreshed.")
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

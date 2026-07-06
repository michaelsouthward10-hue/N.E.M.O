from rich.console import Console
from rich.table import Table

from core.system import SystemManager

console = Console()

system = SystemManager()

status = system.status()
vault = system.scan_vault()

table = Table(title="NEMO System Check")

table.add_column("Component", style="cyan")
table.add_column("Status", style="green")

table.add_row(
    "Vault",
    "✓ Found" if status["vault"] else "✗ Missing"
)

table.add_row(
    "Ollama",
    "✓ Connected" if status["ollama"] else "✗ Offline"
)

console.print(table)

stats = Table(title="Archive Statistics")

stats.add_column("Item")
stats.add_column("Count")

stats.add_row("Folders", str(vault["folders"]))
stats.add_row("Markdown Files", str(vault["markdown"]))
stats.add_row("Other Files", str(vault["other"]))

console.print(stats)
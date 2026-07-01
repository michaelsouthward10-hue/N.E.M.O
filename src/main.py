from rich.console import Console
from rich.table import Table

from system import SystemManager

console = Console()

system = SystemManager()

status = system.status()

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
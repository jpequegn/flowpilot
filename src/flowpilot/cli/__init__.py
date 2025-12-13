"""FlowPilot CLI interface."""

from pathlib import Path

import typer
from rich.console import Console

# CLI App
app = typer.Typer(
    name="flowpilot",
    help="Workflow automation for macOS with Claude Code integration.",
    no_args_is_help=True,
)

# Console for rich output
console = Console()

# Default paths
FLOWPILOT_DIR = Path.home() / ".flowpilot"
WORKFLOWS_DIR = FLOWPILOT_DIR / "workflows"
LOGS_DIR = FLOWPILOT_DIR / "logs"
CONFIG_FILE = FLOWPILOT_DIR / "config.yaml"
DB_FILE = FLOWPILOT_DIR / "flowpilot.db"

# Import commands to register them
from flowpilot.cli.commands import history, init, list_cmd, run, validate  # noqa: E402, F401


@app.command()
def version() -> None:
    """Show FlowPilot version."""
    from flowpilot import __version__

    console.print(f"FlowPilot v{__version__}")


if __name__ == "__main__":
    app()

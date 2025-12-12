"""FlowPilot CLI interface."""

import typer
from rich.console import Console

app = typer.Typer(
    name="flowpilot",
    help="Workflow automation for macOS with Claude Code integration.",
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Show FlowPilot version."""
    from flowpilot import __version__

    console.print(f"FlowPilot v{__version__}")


@app.command()
def init() -> None:
    """Initialize FlowPilot directory structure."""
    console.print("[yellow]init command not yet implemented[/]")


@app.command()
def run(name: str = typer.Argument(..., help="Workflow name to run")) -> None:
    """Execute a workflow."""
    console.print(f"[yellow]run command not yet implemented for: {name}[/]")


@app.command("list")
def list_workflows() -> None:
    """List available workflows."""
    console.print("[yellow]list command not yet implemented[/]")


@app.command()
def validate(name: str = typer.Argument(..., help="Workflow name to validate")) -> None:
    """Validate a workflow YAML file."""
    console.print(f"[yellow]validate command not yet implemented for: {name}[/]")


if __name__ == "__main__":
    app()

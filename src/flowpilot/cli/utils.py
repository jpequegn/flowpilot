"""Utility functions for FlowPilot CLI."""

from pathlib import Path

import typer

from flowpilot.cli import WORKFLOWS_DIR, console


def resolve_workflow_path(name: str) -> Path:
    """Resolve workflow name to file path.

    Args:
        name: Workflow name or path to YAML file.

    Returns:
        Path to the workflow file.

    Raises:
        typer.Exit: If workflow file not found.
    """
    # If it's already a path to a file
    if name.endswith(".yaml") or name.endswith(".yml"):
        path = Path(name)
        if path.exists():
            return path
        console.print(f"[red]Error:[/] Workflow file not found: {path}")
        raise typer.Exit(1)

    # Look in workflows directory
    for ext in [".yaml", ".yml"]:
        path = WORKFLOWS_DIR / f"{name}{ext}"
        if path.exists():
            return path

    # Not found
    console.print(f"[red]Error:[/] Workflow not found: {name}")
    console.print(f"Looked in: {WORKFLOWS_DIR}")
    raise typer.Exit(1)

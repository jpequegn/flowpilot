"""List command for FlowPilot CLI."""

from typing import Any

import typer
from rich.table import Table

from flowpilot.cli import WORKFLOWS_DIR, app, console
from flowpilot.engine.parser import WorkflowParser


@app.command("list")
def list_workflows(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON",
    ),
) -> None:
    """List available workflows.

    Shows all workflow YAML files in the ~/.flowpilot/workflows directory.
    """
    if not WORKFLOWS_DIR.exists():
        if json_output:
            console.print_json(data={"error": "Workflows directory not found", "workflows": []})
        else:
            console.print("[yellow]No workflows directory found.[/]")
            console.print("Run [cyan]flowpilot init[/] to create it.")
        raise typer.Exit(1)

    workflows: list[dict[str, Any]] = []
    parser = WorkflowParser()

    # Find all YAML files
    yaml_files = list(WORKFLOWS_DIR.glob("*.yaml")) + list(WORKFLOWS_DIR.glob("*.yml"))

    for path in sorted(yaml_files):
        try:
            wf = parser.parse_file(path)
            workflows.append(
                {
                    "name": wf.name,
                    "description": wf.description or "",
                    "triggers": [t.type for t in wf.triggers],
                    "nodes": len(wf.nodes),
                    "inputs": len(wf.inputs),
                    "path": str(path),
                }
            )
        except Exception as e:
            workflows.append(
                {
                    "name": path.stem,
                    "error": str(e),
                    "path": str(path),
                }
            )

    if json_output:
        console.print_json(data={"workflows": workflows})
        return

    if not workflows:
        console.print("[yellow]No workflows found.[/]")
        console.print(f"Create workflows in: [cyan]{WORKFLOWS_DIR}[/]")
        return

    # Build table
    table = Table(title="Workflows")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Triggers")
    table.add_column("Nodes", justify="right")

    for wf_info in workflows:
        if "error" in wf_info:
            table.add_row(
                wf_info["name"],
                f"[red]Error: {wf_info['error'][:40]}...[/]"
                if len(wf_info.get("error", "")) > 40
                else f"[red]Error: {wf_info.get('error', '')}[/]",
                "",
                "",
            )
        else:
            triggers = ", ".join(wf_info["triggers"]) if wf_info["triggers"] else "[dim]none[/]"
            table.add_row(
                wf_info["name"],
                wf_info["description"][:50] + "..."
                if len(wf_info["description"]) > 50
                else wf_info["description"],
                triggers,
                str(wf_info["nodes"]),
            )

    console.print(table)
    console.print()
    console.print(f"[dim]Workflows directory: {WORKFLOWS_DIR}[/]")

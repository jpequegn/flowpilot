"""Validate command for FlowPilot CLI."""

import typer
from pydantic import ValidationError

from flowpilot.cli import app, console
from flowpilot.cli.utils import resolve_workflow_path
from flowpilot.engine.parser import WorkflowParser


@app.command()
def validate(
    name: str = typer.Argument(..., help="Workflow name or path to YAML file"),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed workflow information",
    ),
) -> None:
    """Validate a workflow YAML file.

    Checks that the workflow:
    - Has valid YAML syntax
    - Conforms to the FlowPilot schema
    - Has valid node references (depends_on, then/else, etc.)
    """
    path = resolve_workflow_path(name)

    try:
        parser = WorkflowParser()
        workflow = parser.parse_file(path)

        console.print(f"[green]✓[/] Workflow [cyan]{workflow.name}[/] is valid")

        if verbose:
            console.print()
            console.print(f"  [dim]Description:[/] {workflow.description or '(none)'}")
            console.print(f"  [dim]Triggers:[/] {len(workflow.triggers)}")
            console.print(f"  [dim]Nodes:[/] {len(workflow.nodes)}")
            console.print(f"  [dim]Inputs:[/] {len(workflow.inputs)}")

            if workflow.nodes:
                console.print()
                console.print("  [dim]Node IDs:[/]")
                for node in workflow.nodes:
                    node_type = getattr(node, "type", "unknown")
                    console.print(f"    - {node.id} [dim]({node_type})[/]")

    except ValidationError as e:
        console.print(f"[red]✗[/] Validation failed for [cyan]{path.name}[/]:")
        console.print()
        for error in e.errors():
            loc = " → ".join(str(loc_part) for loc_part in error["loc"])
            msg = error["msg"]
            console.print(f"  [red]•[/] [yellow]{loc}[/]: {msg}")
        raise typer.Exit(1)

    except Exception as e:
        console.print(f"[red]✗[/] Error parsing workflow: {e}")
        raise typer.Exit(1)

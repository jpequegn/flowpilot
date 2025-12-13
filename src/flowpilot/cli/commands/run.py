"""Run command for FlowPilot CLI."""

import asyncio
from typing import Any

import typer
from pydantic import ValidationError
from rich.table import Table

# Import node executors to register them with the registry
import flowpilot.engine.nodes  # noqa: F401
from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir, resolve_workflow_path
from flowpilot.engine.context import ExecutionContext
from flowpilot.engine.parser import WorkflowParser
from flowpilot.engine.runner import WorkflowRunner
from flowpilot.storage import Database


@app.command()
def run(
    name: str = typer.Argument(..., help="Workflow name or path to YAML file"),
    inputs: list[str] = typer.Option(
        [],
        "--input",
        "-i",
        help="Input as key=value (can be used multiple times)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output including node outputs",
    ),
) -> None:
    """Execute a workflow.

    Runs all nodes in the workflow in dependency order and displays results.
    Use --input to pass runtime inputs to the workflow.

    Examples:
        flowpilot run my-workflow
        flowpilot run my-workflow --input name=value --input count=10
        flowpilot run my-workflow --json
    """
    path = resolve_workflow_path(name)

    # Parse workflow
    try:
        parser = WorkflowParser()
        workflow = parser.parse_file(path)
    except ValidationError as e:
        console.print(f"[red]✗[/] Invalid workflow [cyan]{path.name}[/]:")
        for error in e.errors():
            loc = " → ".join(str(loc_part) for loc_part in error["loc"])
            console.print(f"  [red]•[/] [yellow]{loc}[/]: {error['msg']}")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]✗[/] Error loading workflow: {e}")
        raise typer.Exit(1)

    # Parse inputs
    input_dict: dict[str, str] = {}
    for inp in inputs:
        if "=" not in inp:
            console.print(f"[red]Error:[/] Invalid input format: {inp}")
            console.print("Use [cyan]--input key=value[/]")
            raise typer.Exit(1)
        key, value = inp.split("=", 1)
        input_dict[key] = value

    if not json_output:
        console.print(f"[cyan]▶[/] Running workflow: [bold]{workflow.name}[/]")
        if input_dict:
            console.print(f"  [dim]Inputs: {input_dict}[/]")
        console.print()

    # Execute workflow with database storage
    try:
        db_path = get_flowpilot_dir() / "flowpilot.db"
        db = Database(db_path) if db_path.exists() else None
        if db:
            db.create_tables()

        runner = WorkflowRunner(db=db)
        context = asyncio.run(
            runner.run(
                workflow,
                input_dict,
                workflow_path=str(path),
                trigger_type="manual",
            )
        )
    except Exception as e:
        if json_output:
            console.print_json(data={"error": str(e), "status": "failed"})
        else:
            console.print(f"[red]✗[/] Execution failed: {e}")
        raise typer.Exit(1)

    # Display results
    if json_output:
        console.print_json(data=_context_to_dict(context))
    else:
        _display_results(context, verbose)

    # Exit code based on any errors
    has_errors = any(r.status == "error" for r in context.nodes.values())
    if has_errors:
        raise typer.Exit(1)


def _context_to_dict(context: ExecutionContext) -> dict[str, Any]:
    """Convert execution context to dictionary for JSON output."""
    return {
        "execution_id": context.execution_id,
        "workflow_name": context.workflow_name,
        "inputs": context.inputs,
        "nodes": {
            node_id: {
                "status": result.status,
                "output": result.output,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "data": result.data,
                "error_message": result.error_message,
                "duration_ms": result.duration_ms,
                "started_at": result.started_at.isoformat() if result.started_at else None,
                "finished_at": result.finished_at.isoformat() if result.finished_at else None,
            }
            for node_id, result in context.nodes.items()
        },
    }


def _display_results(context: ExecutionContext, verbose: bool) -> None:
    """Display execution results in a formatted table."""
    # Count results by status
    success_count = sum(1 for r in context.nodes.values() if r.status == "success")
    error_count = sum(1 for r in context.nodes.values() if r.status == "error")
    skipped_count = sum(1 for r in context.nodes.values() if r.status == "skipped")

    # Build table
    table = Table(title=f"Execution: {context.execution_id[:8]}")
    table.add_column("Node", style="cyan")
    table.add_column("Status")
    table.add_column("Duration", justify="right")
    if verbose:
        table.add_column("Output")

    for node_id, result in context.nodes.items():
        status_display = {
            "success": "[green]✓ success[/]",
            "error": "[red]✗ error[/]",
            "skipped": "[yellow]○ skipped[/]",
            "pending": "[dim]• pending[/]",
            "running": "[blue]◉ running[/]",
        }.get(result.status, f"? {result.status}")

        duration = f"{result.duration_ms}ms" if result.duration_ms else "-"

        if verbose:
            output = ""
            if result.error_message:
                output = f"[red]{result.error_message[:60]}[/]"
            elif result.output:
                output = result.output[:60]
                if len(result.output) > 60:
                    output += "..."
            table.add_row(node_id, status_display, duration, output)
        else:
            table.add_row(node_id, status_display, duration)

    console.print(table)

    # Summary
    console.print()
    total = len(context.nodes)
    summary_parts = []
    if success_count:
        summary_parts.append(f"[green]{success_count} passed[/]")
    if error_count:
        summary_parts.append(f"[red]{error_count} failed[/]")
    if skipped_count:
        summary_parts.append(f"[yellow]{skipped_count} skipped[/]")

    console.print(f"Total: {total} nodes | {' | '.join(summary_parts)}")

    # Show errors in detail if any
    if error_count and not verbose:
        console.print()
        console.print("[dim]Use --verbose to see error details[/]")

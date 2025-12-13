"""History command for FlowPilot CLI."""

from datetime import datetime
from typing import Any

import typer
from rich.table import Table

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir
from flowpilot.storage import (
    Database,
    ExecutionRepository,
    ExecutionStatus,
    NodeExecutionRepository,
)


@app.command()
def history(
    name: str | None = typer.Argument(
        None,
        help="Workflow name to filter by (optional)",
    ),
    limit: int = typer.Option(
        20,
        "--limit",
        "-n",
        help="Maximum number of executions to show",
    ),
    status: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (pending, running, success, failed, cancelled)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON",
    ),
    execution_id: str | None = typer.Option(
        None,
        "--id",
        help="Show details for a specific execution ID",
    ),
) -> None:
    """Show execution history.

    View past workflow executions with status, duration, and node details.

    Examples:
        flowpilot history
        flowpilot history my-workflow
        flowpilot history --limit 50
        flowpilot history --status failed
        flowpilot history --id abc12345
    """
    db_path = get_flowpilot_dir() / "flowpilot.db"

    if not db_path.exists():
        console.print("[yellow]No execution history found.[/]")
        console.print("Run [cyan]flowpilot init[/] to initialize FlowPilot.")
        raise typer.Exit(0)

    db = Database(db_path)

    # If specific execution ID requested, show details
    if execution_id:
        _show_execution_details(db, execution_id, json_output)
        return

    # Parse status filter
    status_filter: ExecutionStatus | None = None
    if status:
        try:
            status_filter = ExecutionStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in ExecutionStatus)
            console.print(f"[red]Error:[/] Invalid status '{status}'")
            console.print(f"Valid values: {valid}")
            raise typer.Exit(1)

    with db.session_scope() as session:
        repo = ExecutionRepository(session)

        if name:
            executions = repo.get_by_workflow(name, limit=limit, status=status_filter)
        else:
            executions = repo.get_recent(limit=limit)
            if status_filter:
                executions = [e for e in executions if e.status == status_filter]

        if json_output:
            data = [_execution_to_dict(e) for e in executions]
            console.print_json(data=data)
            return

        if not executions:
            if name:
                console.print(f"[yellow]No executions found for workflow '{name}'[/]")
            else:
                console.print("[yellow]No execution history found.[/]")
            return

        # Build table
        table = Table(title="Execution History")
        table.add_column("ID", style="dim")
        table.add_column("Workflow", style="cyan")
        table.add_column("Status")
        table.add_column("Trigger")
        table.add_column("Started", style="dim")
        table.add_column("Duration", justify="right")

        for execution in executions:
            status_display = _format_status(execution.status)
            started = _format_datetime(execution.started_at)
            duration = _format_duration(execution.duration_ms)

            table.add_row(
                execution.id[:8],
                execution.workflow_name,
                status_display,
                execution.trigger_type or "-",
                started,
                duration,
            )

        console.print(table)
        console.print()
        console.print(f"[dim]Showing {len(executions)} execution(s)[/]")
        console.print("[dim]Use --id <id> to see execution details[/]")


def _show_execution_details(db: Database, execution_id: str, json_output: bool) -> None:
    """Show details for a specific execution."""
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        node_repo = NodeExecutionRepository(session)

        # Try to find by full ID or prefix
        execution = repo.get_by_id(execution_id)

        if execution is None:
            # Try prefix match
            all_recent = repo.get_recent(limit=100)
            matches = [e for e in all_recent if e.id.startswith(execution_id)]
            if len(matches) == 1:
                execution = matches[0]
            elif len(matches) > 1:
                console.print(f"[red]Error:[/] Multiple executions match '{execution_id}'")
                for m in matches[:5]:
                    console.print(f"  - {m.id}")
                raise typer.Exit(1)

        if execution is None:
            console.print(f"[red]Error:[/] Execution not found: {execution_id}")
            raise typer.Exit(1)

        # Get node executions
        node_executions = node_repo.get_by_execution(execution.id)

        if json_output:
            data = _execution_to_dict(execution)
            data["nodes"] = [_node_execution_to_dict(n) for n in node_executions]
            console.print_json(data=data)
            return

        # Display execution details
        console.print(f"[bold]Execution: {execution.id}[/]")
        console.print()

        details = Table.grid(padding=(0, 2))
        details.add_column(style="dim")
        details.add_column()
        details.add_row("Workflow:", f"[cyan]{execution.workflow_name}[/]")
        details.add_row("Status:", _format_status(execution.status))
        details.add_row("Trigger:", execution.trigger_type or "-")
        details.add_row("Started:", _format_datetime(execution.started_at))
        details.add_row("Finished:", _format_datetime(execution.finished_at))
        details.add_row("Duration:", _format_duration(execution.duration_ms))
        if execution.error:
            details.add_row("Error:", f"[red]{execution.error}[/]")
        if execution.inputs:
            details.add_row("Inputs:", str(execution.inputs))
        console.print(details)

        if node_executions:
            console.print()
            node_table = Table(title="Node Executions")
            node_table.add_column("Node", style="cyan")
            node_table.add_column("Type")
            node_table.add_column("Status")
            node_table.add_column("Duration", justify="right")
            node_table.add_column("Error")

            for node_exec in node_executions:
                status_display = {
                    "success": "[green]✓[/]",
                    "error": "[red]✗[/]",
                    "skipped": "[yellow]○[/]",
                }.get(node_exec.status, f"? {node_exec.status}")

                error_display = ""
                if node_exec.error:
                    error_display = f"[red]{node_exec.error[:40]}...[/]" if len(node_exec.error) > 40 else f"[red]{node_exec.error}[/]"

                node_table.add_row(
                    node_exec.node_id,
                    node_exec.node_type,
                    status_display,
                    _format_duration(node_exec.duration_ms),
                    error_display,
                )

            console.print(node_table)


def _format_status(status: ExecutionStatus) -> str:
    """Format status for display."""
    return {
        ExecutionStatus.PENDING: "[dim]● pending[/]",
        ExecutionStatus.RUNNING: "[blue]◉ running[/]",
        ExecutionStatus.SUCCESS: "[green]✓ success[/]",
        ExecutionStatus.FAILED: "[red]✗ failed[/]",
        ExecutionStatus.CANCELLED: "[yellow]○ cancelled[/]",
    }.get(status, str(status))


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_duration(ms: int | None) -> str:
    """Format duration for display."""
    if ms is None:
        return "-"
    if ms < 1000:
        return f"{ms}ms"
    if ms < 60000:
        return f"{ms / 1000:.1f}s"
    minutes = ms // 60000
    seconds = (ms % 60000) / 1000
    return f"{minutes}m {seconds:.0f}s"


def _execution_to_dict(execution: Any) -> dict[str, Any]:
    """Convert execution to dictionary for JSON output."""
    return {
        "id": execution.id,
        "workflow_name": execution.workflow_name,
        "workflow_path": execution.workflow_path,
        "status": execution.status.value,
        "trigger_type": execution.trigger_type,
        "inputs": execution.inputs,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
        "duration_ms": execution.duration_ms,
        "error": execution.error,
    }


def _node_execution_to_dict(node_exec: Any) -> dict[str, Any]:
    """Convert node execution to dictionary for JSON output."""
    return {
        "node_id": node_exec.node_id,
        "node_type": node_exec.node_type,
        "status": node_exec.status,
        "started_at": node_exec.started_at.isoformat() if node_exec.started_at else None,
        "finished_at": node_exec.finished_at.isoformat() if node_exec.finished_at else None,
        "duration_ms": node_exec.duration_ms,
        "stdout": node_exec.stdout,
        "stderr": node_exec.stderr,
        "output": node_exec.output,
        "error": node_exec.error,
    }

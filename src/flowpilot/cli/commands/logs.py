"""Logs command for FlowPilot CLI."""

import time
from datetime import datetime
from typing import Any

import typer
from rich.text import Text

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir
from flowpilot.storage import Database, ExecutionRepository, NodeExecutionRepository


@app.command()
def logs(
    name: str = typer.Argument(..., help="Workflow name to view logs for"),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow log output (tail -f style)",
    ),
    lines: int = typer.Option(
        50,
        "--lines",
        "-n",
        help="Number of log lines to show",
    ),
    execution_id: str | None = typer.Option(
        None,
        "--execution",
        "-e",
        help="View logs for a specific execution ID",
    ),
) -> None:
    """View execution logs for a workflow.

    Shows recent execution logs with stdout/stderr output from nodes.

    Examples:
        flowpilot logs my-workflow
        flowpilot logs my-workflow -n 100
        flowpilot logs my-workflow -f
        flowpilot logs my-workflow -e abc12345
    """
    db_path = get_flowpilot_dir() / "flowpilot.db"

    if not db_path.exists():
        console.print("[yellow]No execution history found.[/]")
        console.print("Run [cyan]flowpilot init[/] to initialize FlowPilot.")
        raise typer.Exit(0)

    db = Database(db_path)

    if execution_id:
        _show_execution_logs(db, execution_id)
        return

    if follow:
        _follow_logs(db, name)
    else:
        _show_recent_logs(db, name, lines)


def _show_recent_logs(db: Database, workflow_name: str, lines: int) -> None:
    """Show recent execution logs for a workflow."""
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        node_repo = NodeExecutionRepository(session)

        executions = repo.get_by_workflow(workflow_name, limit=lines)

        if not executions:
            console.print(f"[yellow]No executions found for workflow '{workflow_name}'[/]")
            return

        console.print(f"[bold]Logs for workflow: {workflow_name}[/]")
        console.print()

        for execution in reversed(executions):
            _print_execution_logs(execution, node_repo)


def _show_execution_logs(db: Database, execution_id: str) -> None:
    """Show logs for a specific execution."""
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

        _print_execution_logs(execution, node_repo)


def _follow_logs(db: Database, workflow_name: str) -> None:
    """Follow logs in real-time (tail -f style)."""
    last_execution_id: str | None = None
    last_seen_time: datetime | None = None

    console.print(f"[bold]Following logs for: {workflow_name}[/]")
    console.print("[dim]Press Ctrl+C to stop[/]")
    console.print()

    try:
        while True:
            with db.session_scope() as session:
                repo = ExecutionRepository(session)
                node_repo = NodeExecutionRepository(session)

                # Get recent executions
                executions = repo.get_by_workflow(workflow_name, limit=5)

                if executions:
                    for execution in reversed(executions):
                        # Check if this is a new execution or updated execution
                        if last_execution_id is None:
                            # First iteration - show latest execution
                            _print_execution_logs(execution, node_repo)
                            last_execution_id = execution.id
                            last_seen_time = execution.finished_at or execution.started_at
                        elif execution.id != last_execution_id:
                            # New execution started
                            exec_time = execution.finished_at or execution.started_at
                            if last_seen_time is None or (exec_time and exec_time > last_seen_time):
                                console.print()
                                _print_execution_logs(execution, node_repo)
                                last_execution_id = execution.id
                                last_seen_time = exec_time

            time.sleep(2)  # Poll every 2 seconds

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped following logs.[/]")


def _print_execution_logs(execution: Any, node_repo: NodeExecutionRepository) -> None:
    """Print logs for a single execution."""
    # Header with status color
    status_color = "green" if execution.status.value == "success" else "red"
    if execution.status.value == "running":
        status_color = "yellow"
    elif execution.status.value == "pending":
        status_color = "dim"

    header = Text()
    header.append("═══ ", style="dim")
    header.append(execution.id[:8], style="bold")
    header.append(f" [{execution.status.value}]", style=status_color)
    header.append(" ═══", style="dim")
    console.print(header)

    # Timestamp
    started = execution.started_at.strftime("%Y-%m-%d %H:%M:%S") if execution.started_at else "-"
    duration = f"{execution.duration_ms}ms" if execution.duration_ms else "-"
    console.print(f"[dim]Started: {started} | Duration: {duration}[/]")

    # Get node executions
    node_executions = node_repo.get_by_execution(execution.id)

    if not node_executions:
        console.print("[dim]  No node output[/]")
        console.print()
        return

    # Node outputs
    for node_exec in node_executions:
        icon = "[green]✓[/]" if node_exec.status == "success" else "[red]✗[/]"
        if node_exec.status == "skipped":
            icon = "[yellow]○[/]"

        node_duration = f"{node_exec.duration_ms}ms" if node_exec.duration_ms else "-"
        console.print(
            f"\n{icon} [cyan]{node_exec.node_id}[/] ({node_exec.node_type}) - {node_duration}"
        )

        # Show stdout
        if node_exec.stdout:
            for line in node_exec.stdout.split("\n"):
                if line.strip():
                    console.print(f"  [dim]{line}[/]")

        # Show stderr
        if node_exec.stderr:
            for line in node_exec.stderr.split("\n"):
                if line.strip():
                    console.print(f"  [red dim]{line}[/]")

        # Show error
        if node_exec.error:
            console.print(f"  [red]Error: {node_exec.error}[/]")

        # Show output (for nodes like http that return data)
        if (
            node_exec.output
            and isinstance(node_exec.output, dict)
            and node_exec.node_type in ("http", "file-read", "shell")
        ):
            output_preview = str(node_exec.output)
            if len(output_preview) > 100:
                output_preview = output_preview[:100] + "..."
            console.print(f"  [dim]Output: {output_preview}[/]")

    console.print()


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

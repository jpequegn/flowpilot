"""Logs command for FlowPilot CLI."""

from __future__ import annotations

import time
from datetime import datetime
from typing import TYPE_CHECKING

import typer
from rich.text import Text

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir
from flowpilot.storage import (
    Database,
    ExecutionRepository,
    ExecutionStatus,
    NodeExecutionRepository,
)

if TYPE_CHECKING:
    from flowpilot.storage import Execution, NodeExecution


@app.command()
def logs(
    name: str = typer.Argument(None, help="Workflow name"),
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
        help="Number of recent lines/executions to show",
    ),
    execution_id: str | None = typer.Option(
        None,
        "--execution",
        "-e",
        help="Show logs for a specific execution ID",
    ),
    server: bool = typer.Option(
        False,
        "--server",
        "-s",
        help="View server logs instead of workflow logs",
    ),
) -> None:
    """View execution logs for a workflow or server logs.

    Shows stdout, stderr, and node outputs from workflow executions.
    Use -f/--follow to tail logs in real-time.
    Use --server to view the FlowPilot server logs.

    Examples:
        flowpilot logs my-workflow
        flowpilot logs my-workflow -f
        flowpilot logs my-workflow -n 5
        flowpilot logs my-workflow -e abc12345
        flowpilot logs --server
        flowpilot logs --server -f
    """
    if server:
        _show_server_logs(follow, lines)
        return

    if not name:
        console.print("[red]Error:[/] Workflow name is required (or use --server)")
        raise typer.Exit(1)

    db_path = get_flowpilot_dir() / "flowpilot.db"

    if not db_path.exists():
        console.print("[yellow]No execution logs found.[/]")
        console.print("Run [cyan]flowpilot init[/] to initialize FlowPilot.")
        raise typer.Exit(0)

    db = Database(db_path)

    if execution_id:
        # Show logs for specific execution
        _show_execution_logs(db, name, execution_id)
        return

    if follow:
        # Follow mode - tail logs
        _follow_logs(db, name)
    else:
        # Show recent executions
        _show_recent_logs(db, name, lines)


def _show_server_logs(follow: bool, lines: int) -> None:
    """Show server logs from the log file.

    Args:
        follow: Whether to follow the log output.
        lines: Number of recent lines to show.
    """
    log_dir = get_flowpilot_dir() / "logs"
    server_log = log_dir / "server.log"
    error_log = log_dir / "server.error.log"

    if not server_log.exists() and not error_log.exists():
        console.print("[yellow]No server logs found.[/]")
        console.print("Start the server with [cyan]flowpilot serve[/] to generate logs.")
        return

    if follow:
        # Follow mode - tail logs
        console.print("[dim]Following server logs... (Ctrl+C to stop)[/]")
        console.print()

        last_pos: dict[str, int] = {}

        try:
            while True:
                for log_file, prefix in [(server_log, ""), (error_log, "[stderr] ")]:
                    if not log_file.exists():
                        continue

                    current_size = log_file.stat().st_size
                    last_position = last_pos.get(str(log_file), 0)

                    if current_size > last_position:
                        with log_file.open("r") as f:
                            f.seek(last_position)
                            new_content = f.read()
                            for line in new_content.splitlines():
                                if line.strip():
                                    if prefix:
                                        console.print(f"[yellow]{prefix}{line}[/]")
                                    else:
                                        console.print(line)
                            last_pos[str(log_file)] = f.tell()

                time.sleep(0.5)

        except KeyboardInterrupt:
            console.print("\n[dim]Stopped following logs.[/]")
    else:
        # Show recent lines
        all_lines: list[tuple[str, str]] = []

        for log_file, style in [(server_log, ""), (error_log, "yellow")]:
            if not log_file.exists():
                continue

            with log_file.open("r") as f:
                file_lines = f.readlines()
                for line in file_lines:
                    all_lines.append((line.rstrip(), style))

        # Show last N lines
        if not all_lines:
            console.print("[yellow]Server logs are empty.[/]")
            return

        console.print("[bold]FlowPilot Server Logs[/]")
        console.print()

        for line, style in all_lines[-lines:]:
            if line.strip():
                if style:
                    console.print(f"[{style}]{line}[/]")
                else:
                    console.print(line)


def _show_execution_logs(db: Database, workflow_name: str, execution_id: str) -> None:
    """Show logs for a specific execution."""
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        node_repo = NodeExecutionRepository(session)

        # Try to find by full ID or prefix
        execution = repo.get_by_id(execution_id)

        if execution is None:
            # Try prefix match within workflow
            executions = repo.get_by_workflow(workflow_name, limit=100)
            matches = [e for e in executions if e.id.startswith(execution_id)]
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

        if execution.workflow_name != workflow_name:
            console.print(
                f"[red]Error:[/] Execution {execution_id} belongs to "
                f"'{execution.workflow_name}', not '{workflow_name}'"
            )
            raise typer.Exit(1)

        node_executions = node_repo.get_by_execution(execution.id)
        _print_execution_logs(execution, node_executions)


def _show_recent_logs(db: Database, workflow_name: str, count: int) -> None:
    """Show logs for recent executions."""
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        node_repo = NodeExecutionRepository(session)

        executions = repo.get_by_workflow(workflow_name, limit=count)

        if not executions:
            console.print(f"[yellow]No executions found for '{workflow_name}'[/]")
            console.print("Run the workflow with [cyan]flowpilot run {workflow_name}[/]")
            return

        # Show in chronological order (oldest first)
        for execution in reversed(executions):
            node_executions = node_repo.get_by_execution(execution.id)
            _print_execution_logs(execution, node_executions)
            console.print()  # Separator between executions


def _follow_logs(db: Database, workflow_name: str) -> None:
    """Follow logs in real-time."""
    console.print(f"[dim]Following logs for '{workflow_name}'... (Ctrl+C to stop)[/]")
    console.print()

    last_execution_id: str | None = None
    seen_node_ids: set[str] = set()

    try:
        while True:
            with db.session_scope() as session:
                repo = ExecutionRepository(session)
                node_repo = NodeExecutionRepository(session)

                # Get most recent execution
                executions = repo.get_by_workflow(workflow_name, limit=1)

                if executions:
                    execution = executions[0]

                    # Check if this is a new execution
                    if execution.id != last_execution_id:
                        # New execution started
                        if last_execution_id is not None:
                            console.print()  # Separator

                        _print_execution_header(execution)
                        last_execution_id = execution.id
                        seen_node_ids.clear()

                    # Get node executions
                    node_executions = node_repo.get_by_execution(execution.id)

                    # Print new node outputs
                    for node_exec in node_executions:
                        node_key = f"{execution.id}:{node_exec.node_id}"
                        if node_key not in seen_node_ids:
                            _print_node_output(node_exec)
                            seen_node_ids.add(node_key)

                    # Check if execution finished
                    if execution.status in (
                        ExecutionStatus.SUCCESS,
                        ExecutionStatus.FAILED,
                        ExecutionStatus.CANCELLED,
                    ):
                        _print_execution_footer(execution)

            time.sleep(1)  # Poll every second

    except KeyboardInterrupt:
        console.print("\n[dim]Stopped following logs.[/]")


def _print_execution_logs(
    execution: Execution,
    node_executions: list[NodeExecution],
) -> None:
    """Print full logs for an execution."""
    _print_execution_header(execution)

    for node_exec in node_executions:
        _print_node_output(node_exec)

    _print_execution_footer(execution)


def _print_execution_header(execution: Execution) -> None:
    """Print execution header."""
    status_color = _get_status_color(execution.status)
    status_icon = _get_status_icon(execution.status)

    header = Text()
    header.append("═══ ", style="dim")
    header.append(f"{execution.id[:8]}", style="bold")
    header.append(" ═══ ", style="dim")
    header.append(f"{status_icon} ", style=status_color)
    header.append(f"{execution.status.value}", style=status_color)

    console.print(header)
    console.print(f"[dim]Started: {_format_datetime(execution.started_at)}[/]")
    if execution.trigger_type:
        console.print(f"[dim]Trigger: {execution.trigger_type}[/]")


def _print_execution_footer(execution: Execution) -> None:
    """Print execution footer."""
    if execution.finished_at:
        duration = _format_duration(execution.duration_ms)
        console.print(f"[dim]Finished: {_format_datetime(execution.finished_at)} ({duration})[/]")

    if execution.error:
        console.print(f"[red]Error: {execution.error}[/]")


def _print_node_output(node_exec: NodeExecution) -> None:
    """Print output for a single node execution."""
    status_icon = "✓" if node_exec.status == "success" else "✗"
    status_color = "green" if node_exec.status == "success" else "red"
    duration = _format_duration(node_exec.duration_ms)

    # Node header
    header = Text()
    header.append(f"\n{status_icon} ", style=status_color)
    header.append(f"{node_exec.node_id}", style="cyan bold")
    header.append(f" ({node_exec.node_type})", style="dim")
    header.append(f" - {duration}", style="dim")
    console.print(header)

    # Build content for panel
    content_parts = []

    # Stdout
    if node_exec.stdout and node_exec.stdout.strip():
        stdout_text = Text(node_exec.stdout.strip(), style="")
        content_parts.append(stdout_text)

    # Stderr
    if node_exec.stderr and node_exec.stderr.strip():
        stderr_text = Text()
        stderr_text.append("[stderr]\n", style="dim yellow")
        stderr_text.append(node_exec.stderr.strip(), style="yellow")
        content_parts.append(stderr_text)

    # Output (structured)
    if node_exec.output:
        output_str = str(node_exec.output)
        if len(output_str) > 500:
            output_str = output_str[:500] + "..."
        output_text = Text()
        output_text.append("[output]\n", style="dim cyan")
        output_text.append(output_str, style="")
        content_parts.append(output_text)

    # Error
    if node_exec.error:
        error_text = Text()
        error_text.append("[error]\n", style="dim red")
        error_text.append(node_exec.error, style="red")
        content_parts.append(error_text)

    # Print content if any
    if content_parts:
        # Join parts with newlines
        combined = Text()
        for i, part in enumerate(content_parts):
            if i > 0:
                combined.append("\n")
            combined.append(part)

        # Indent the content
        for line in str(combined).split("\n"):
            if line.strip():
                console.print(f"  {line}")


def _get_status_color(status: ExecutionStatus) -> str:
    """Get color for status."""
    return {
        ExecutionStatus.PENDING: "dim",
        ExecutionStatus.RUNNING: "blue",
        ExecutionStatus.SUCCESS: "green",
        ExecutionStatus.FAILED: "red",
        ExecutionStatus.CANCELLED: "yellow",
    }.get(status, "white")


def _get_status_icon(status: ExecutionStatus) -> str:
    """Get icon for status."""
    return {
        ExecutionStatus.PENDING: "●",
        ExecutionStatus.RUNNING: "◉",
        ExecutionStatus.SUCCESS: "✓",
        ExecutionStatus.FAILED: "✗",
        ExecutionStatus.CANCELLED: "○",
    }.get(status, "?")


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

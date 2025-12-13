"""Schedule commands for FlowPilot CLI."""

from datetime import datetime
from typing import Any

import typer
from rich.table import Table

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir


def _get_schedule_manager() -> Any:
    """Get a ScheduleManager instance."""
    from flowpilot.scheduler import FileWatchService, ScheduleManager, SchedulerService
    from flowpilot.storage import Database

    flowpilot_dir = get_flowpilot_dir()
    db_path = flowpilot_dir / "flowpilot.db"
    workflows_dir = flowpilot_dir / "workflows"

    if not db_path.exists():
        console.print("[red]Error:[/] FlowPilot not initialized.")
        console.print("Run [cyan]flowpilot init[/] first.")
        raise typer.Exit(1)

    db = Database(db_path)
    db.create_tables()

    # Use a separate job store database for APScheduler
    scheduler_db_url = f"sqlite:///{flowpilot_dir / 'scheduler.db'}"
    scheduler = SchedulerService(scheduler_db_url, workflows_dir)

    # Create file watcher service
    file_watcher = FileWatchService()

    return ScheduleManager(scheduler, db, file_watcher, workflows_dir)


@app.command()
def enable(
    name: str = typer.Argument(..., help="Workflow name to enable scheduling for"),
) -> None:
    """Enable scheduling for a workflow.

    Schedules the workflow based on its cron, interval, or file-watch triggers.
    The workflow must have at least one schedulable trigger defined.

    Examples:
        flowpilot enable my-workflow
    """
    from flowpilot.scheduler import ScheduleManagerError

    manager = _get_schedule_manager()

    try:
        result = manager.enable_workflow(name)

        console.print(f"[green]✓[/] Enabled schedule for [cyan]{name}[/]")

        # Show scheduled triggers (cron/interval)
        for sched in result.get("scheduled", []):
            console.print(f"  Schedule: {sched['trigger']}")
            if sched.get("next_run"):
                console.print(f"  Next run: {_format_datetime(sched['next_run'])}")

        # Show file watches
        for fw in result.get("file_watches", []):
            events = ", ".join(fw["events"])
            pattern = fw.get("pattern") or "*"
            console.print(f"  File watch: {fw['path']}")
            console.print(f"    Events: {events}, Pattern: {pattern}")

    except ScheduleManagerError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def disable(
    name: str = typer.Argument(..., help="Workflow name to disable scheduling for"),
) -> None:
    """Disable scheduling for a workflow.

    Removes the workflow from the scheduler and file watcher. The workflow
    can still be run manually with `flowpilot run`.

    Examples:
        flowpilot disable my-workflow
    """
    manager = _get_schedule_manager()

    result = manager.disable_workflow(name)

    if result["schedule_removed"] or result["file_watch_removed"]:
        console.print(f"[green]✓[/] Disabled schedule for [cyan]{name}[/]")
        if result["schedule_removed"]:
            console.print("  Removed cron/interval schedule")
        if result["file_watch_removed"]:
            console.print("  Removed file watch")
    else:
        console.print(f"[yellow]![/] No schedule found for [cyan]{name}[/]")


@app.command()
def status(
    name: str | None = typer.Argument(
        None,
        help="Workflow name to check (shows all if omitted)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON",
    ),
) -> None:
    """Show schedule status for workflows.

    Displays enabled schedules with next run times, last run status,
    trigger configuration, and file watches.

    Examples:
        flowpilot status
        flowpilot status my-workflow
        flowpilot status --json
    """
    manager = _get_schedule_manager()
    schedules = manager.get_status(name)

    if json_output:
        data = [
            {
                "name": s["name"],
                "enabled": s["enabled"],
                "next_run": s["next_run"].isoformat() if s["next_run"] else None,
                "trigger": s["trigger"],
                "file_watch": s.get("file_watch"),
                "last_run": s["last_run"].isoformat() if s["last_run"] else None,
                "last_status": s["last_status"],
            }
            for s in schedules
        ]
        console.print_json(data=data)
        return

    if not schedules:
        if name:
            console.print(f"[yellow]No schedule found for workflow:[/] {name}")
        else:
            console.print("[yellow]No scheduled workflows.[/]")
            console.print("Use [cyan]flowpilot enable <name>[/] to schedule a workflow.")
        return

    table = Table(title="Scheduled Workflows")
    table.add_column("Workflow", style="cyan")
    table.add_column("Status")
    table.add_column("Type")
    table.add_column("Next Run / Watch Path")
    table.add_column("Last Run")
    table.add_column("Last Status")

    for sched in schedules:
        status_display = "[green]● enabled[/]" if sched["enabled"] else "[dim]○ disabled[/]"

        # Determine trigger type and info
        file_watch = sched.get("file_watch")
        trigger = sched.get("trigger")

        if file_watch and trigger:
            trigger_type = "mixed"
            next_run_or_path = _format_datetime(sched["next_run"]) if sched["next_run"] else "-"
        elif file_watch:
            trigger_type = "file-watch"
            watch_path = file_watch.get("path", "-")
            if len(watch_path) > 25:
                watch_path = "..." + watch_path[-22:]
            next_run_or_path = f"📁 {watch_path}"
        elif trigger:
            trigger_type = "schedule"
            next_run_or_path = _format_datetime(sched["next_run"]) if sched["next_run"] else "-"
        else:
            trigger_type = "-"
            next_run_or_path = "-"

        last_run = _format_datetime(sched["last_run"]) if sched["last_run"] else "-"

        last_status = "-"
        if sched["last_status"]:
            if sched["last_status"] == "success":
                last_status = "[green]✓[/]"
            elif sched["last_status"] == "failed":
                last_status = "[red]✗[/]"
            else:
                last_status = sched["last_status"]

        table.add_row(
            sched["name"],
            status_display,
            trigger_type,
            next_run_or_path,
            last_run,
            last_status,
        )

    console.print(table)


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

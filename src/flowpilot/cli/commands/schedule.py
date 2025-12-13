"""Schedule commands for FlowPilot CLI."""

from datetime import datetime
from typing import Any

import typer
from rich.table import Table

from flowpilot.cli import app, console
from flowpilot.cli.utils import get_flowpilot_dir


def _get_schedule_manager() -> Any:
    """Get a ScheduleManager instance."""
    from flowpilot.scheduler import ScheduleManager, SchedulerService
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

    return ScheduleManager(scheduler, db, workflows_dir)


@app.command()
def enable(
    name: str = typer.Argument(..., help="Workflow name to enable scheduling for"),
) -> None:
    """Enable scheduling for a workflow.

    Schedules the workflow based on its cron or interval triggers.
    The workflow must have at least one schedulable trigger defined.

    Examples:
        flowpilot enable my-workflow
    """
    from flowpilot.scheduler import ScheduleManagerError

    manager = _get_schedule_manager()

    try:
        result = manager.enable_workflow(name)

        console.print(f"[green]✓[/] Enabled schedule for [cyan]{name}[/]")
        console.print(f"  Trigger: {result['trigger']}")
        if result["next_run"]:
            console.print(f"  Next run: {_format_datetime(result['next_run'])}")

    except ScheduleManagerError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)


@app.command()
def disable(
    name: str = typer.Argument(..., help="Workflow name to disable scheduling for"),
) -> None:
    """Disable scheduling for a workflow.

    Removes the workflow from the scheduler. The workflow can still
    be run manually with `flowpilot run`.

    Examples:
        flowpilot disable my-workflow
    """
    manager = _get_schedule_manager()

    if manager.disable_workflow(name):
        console.print(f"[green]✓[/] Disabled schedule for [cyan]{name}[/]")
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
    and trigger configuration.

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
    table.add_column("Next Run")
    table.add_column("Last Run")
    table.add_column("Last Status")
    table.add_column("Trigger", style="dim")

    for sched in schedules:
        status_display = "[green]● enabled[/]" if sched["enabled"] else "[dim]○ disabled[/]"

        next_run = _format_datetime(sched["next_run"]) if sched["next_run"] else "-"
        last_run = _format_datetime(sched["last_run"]) if sched["last_run"] else "-"

        last_status = "-"
        if sched["last_status"]:
            if sched["last_status"] == "success":
                last_status = "[green]✓[/]"
            elif sched["last_status"] == "failed":
                last_status = "[red]✗[/]"
            else:
                last_status = sched["last_status"]

        trigger = sched["trigger"] or "-"
        if len(trigger) > 30:
            trigger = trigger[:27] + "..."

        table.add_row(
            sched["name"],
            status_display,
            next_run,
            last_run,
            last_status,
            trigger,
        )

    console.print(table)


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime for display."""
    if dt is None:
        return "-"
    return dt.strftime("%Y-%m-%d %H:%M:%S")

"""APScheduler service for FlowPilot workflow scheduling."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler

if TYPE_CHECKING:
    from datetime import datetime

    from apscheduler.schedulers.base import BaseScheduler
    from apscheduler.triggers.cron import CronTrigger as APCronTrigger
    from apscheduler.triggers.interval import IntervalTrigger as APIntervalTrigger

    from flowpilot.engine.runner import WorkflowRunner
    from flowpilot.models import Workflow

logger = logging.getLogger(__name__)

# Global reference to runner for job execution (set via set_global_runner)
_global_runner: WorkflowRunner | None = None


def set_global_runner(runner: WorkflowRunner | None) -> None:
    """Set the global workflow runner for scheduled job execution.

    Args:
        runner: WorkflowRunner instance to use for executing workflows.
    """
    global _global_runner
    _global_runner = runner


def _execute_scheduled_workflow(workflow_name: str, workflow_path: str) -> None:
    """Job function to execute a workflow.

    This is a module-level function to avoid serialization issues with APScheduler.

    Args:
        workflow_name: Name of the workflow.
        workflow_path: Path to the workflow file.
    """
    import asyncio

    from flowpilot.engine.parser import WorkflowParser

    if _global_runner is None:
        logger.error(f"Cannot execute workflow '{workflow_name}': no runner configured")
        return

    path = Path(workflow_path)
    if not path.exists():
        logger.error(f"Workflow file not found: {path}")
        return

    try:
        parser = WorkflowParser()
        workflow = parser.parse_file(path)

        logger.info(f"Executing scheduled workflow: {workflow_name}")

        # Run the async workflow in an event loop
        asyncio.run(
            _global_runner.run(
                workflow,
                workflow_path=str(path),
                trigger_type="scheduled",
            )
        )
        logger.info(f"Completed scheduled workflow: {workflow_name}")

    except Exception as e:
        logger.exception(f"Failed to execute scheduled workflow '{workflow_name}': {e}")


class SchedulerService:
    """APScheduler-based scheduling service for workflows.

    Manages workflow scheduling with cron and interval triggers,
    with job persistence via SQLite.
    """

    def __init__(
        self,
        db_url: str,
        workflows_dir: Path | None = None,
        scheduler_type: Literal["asyncio", "background"] = "background",
    ) -> None:
        """Initialize the scheduler service.

        Args:
            db_url: SQLAlchemy database URL for job persistence.
            workflows_dir: Directory containing workflow files.
            scheduler_type: Type of scheduler to use ("asyncio" or "background").
        """
        jobstores = {"default": SQLAlchemyJobStore(url=db_url)}

        job_defaults = {
            "coalesce": True,  # Combine missed runs into one
            "max_instances": 1,  # Only one instance at a time
            "misfire_grace_time": 60,  # Allow 60s late execution
        }

        scheduler_class: type[BaseScheduler] = (
            AsyncIOScheduler if scheduler_type == "asyncio" else BackgroundScheduler
        )

        self._scheduler: BaseScheduler = scheduler_class(
            jobstores=jobstores,
            job_defaults=job_defaults,
        )

        self._workflows_dir = workflows_dir or (Path.home() / ".flowpilot" / "workflows")
        self._runner: WorkflowRunner | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def set_runner(self, runner: WorkflowRunner) -> None:
        """Set the workflow runner for job execution.

        Args:
            runner: WorkflowRunner instance to execute workflows.
        """
        self._runner = runner
        # Also set the global runner for the module-level job function
        set_global_runner(runner)

    def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            return

        self._scheduler.start()
        self._running = True
        logger.info("Scheduler started")

    def shutdown(self, wait: bool = True) -> None:
        """Gracefully shutdown the scheduler.

        Args:
            wait: Whether to wait for running jobs to complete.
        """
        if not self._running:
            return

        self._scheduler.shutdown(wait=wait)
        self._running = False
        logger.info("Scheduler stopped")

    def schedule_workflow(
        self,
        workflow: Workflow,
        trigger: APCronTrigger | APIntervalTrigger,
        workflow_path: str | None = None,
    ) -> str:
        """Schedule a workflow execution.

        Args:
            workflow: The workflow to schedule.
            trigger: APScheduler trigger (cron or interval).
            workflow_path: Path to workflow file (for persistence).

        Returns:
            The job ID.
        """
        job_id = f"workflow:{workflow.name}"

        job = self._scheduler.add_job(
            _execute_scheduled_workflow,
            trigger=trigger,
            id=job_id,
            name=workflow.name,
            kwargs={
                "workflow_name": workflow.name,
                "workflow_path": workflow_path
                or str(self._workflows_dir / f"{workflow.name}.yaml"),
            },
            replace_existing=True,
        )

        logger.info(f"Scheduled workflow '{workflow.name}' with job ID: {job.id}")
        return job.id

    def remove_schedule(self, workflow_name: str) -> bool:
        """Remove a workflow schedule.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            True if removed, False if not found.
        """
        job_id = f"workflow:{workflow_name}"
        job = self._scheduler.get_job(job_id)

        if job:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed schedule for workflow: {workflow_name}")
            return True

        return False

    def pause_schedule(self, workflow_name: str) -> bool:
        """Pause a workflow schedule.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            True if paused, False if not found.
        """
        job_id = f"workflow:{workflow_name}"
        job = self._scheduler.get_job(job_id)

        if job:
            self._scheduler.pause_job(job_id)
            logger.info(f"Paused schedule for workflow: {workflow_name}")
            return True

        return False

    def resume_schedule(self, workflow_name: str) -> bool:
        """Resume a paused workflow schedule.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            True if resumed, False if not found.
        """
        job_id = f"workflow:{workflow_name}"
        job = self._scheduler.get_job(job_id)

        if job:
            self._scheduler.resume_job(job_id)
            logger.info(f"Resumed schedule for workflow: {workflow_name}")
            return True

        return False

    def get_schedules(self) -> list[dict[str, Any]]:
        """Get all scheduled workflows.

        Returns:
            List of schedule information dictionaries.
        """
        jobs = self._scheduler.get_jobs()

        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "trigger": str(job.trigger),
                "paused": job.next_run_time is None,
            }
            for job in jobs
        ]

    def get_schedule(self, workflow_name: str) -> dict[str, Any] | None:
        """Get schedule info for a specific workflow.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            Schedule information or None if not found.
        """
        job_id = f"workflow:{workflow_name}"
        job = self._scheduler.get_job(job_id)

        if job:
            return {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time,
                "trigger": str(job.trigger),
                "paused": job.next_run_time is None,
            }

        return None

    def get_next_run(self, workflow_name: str) -> datetime | None:
        """Get next run time for a workflow.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            Next run datetime or None if not scheduled.
        """
        job_id = f"workflow:{workflow_name}"
        job = self._scheduler.get_job(job_id)

        return job.next_run_time if job else None

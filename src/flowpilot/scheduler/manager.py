"""High-level schedule management for FlowPilot workflows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from flowpilot.engine.parser import WorkflowParser
from flowpilot.storage import Database, Schedule, ScheduleRepository

from .service import SchedulerService  # noqa: TC001
from .triggers import is_schedulable, parse_trigger

if TYPE_CHECKING:
    from flowpilot.models import Workflow

logger = logging.getLogger(__name__)


class ScheduleManagerError(Exception):
    """Error in schedule management."""


class ScheduleManager:
    """High-level interface for managing workflow schedules.

    Coordinates between the APScheduler service and the database
    for persistent schedule management.
    """

    def __init__(
        self,
        scheduler: SchedulerService,
        db: Database,
        workflows_dir: Path | None = None,
    ) -> None:
        """Initialize the schedule manager.

        Args:
            scheduler: APScheduler service instance.
            db: Database for schedule persistence.
            workflows_dir: Directory containing workflow files.
        """
        self._scheduler = scheduler
        self._db = db
        self._workflows_dir = workflows_dir or (Path.home() / ".flowpilot" / "workflows")
        self._parser = WorkflowParser()

    def _find_workflow_path(self, workflow_name: str) -> Path:
        """Find the path to a workflow file.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            Path to the workflow file.

        Raises:
            ScheduleManagerError: If workflow file not found.
        """
        for ext in [".yaml", ".yml"]:
            path = self._workflows_dir / f"{workflow_name}{ext}"
            if path.exists():
                return path

        msg = f"Workflow not found: {workflow_name}"
        raise ScheduleManagerError(msg)

    def _load_workflow(self, workflow_name: str) -> tuple[Workflow, Path]:
        """Load a workflow by name.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            Tuple of (Workflow, Path).

        Raises:
            ScheduleManagerError: If workflow not found or invalid.
        """
        path = self._find_workflow_path(workflow_name)

        try:
            workflow = self._parser.parse_file(path)
            return workflow, path
        except Exception as e:
            msg = f"Failed to load workflow '{workflow_name}': {e}"
            raise ScheduleManagerError(msg) from e

    def enable_workflow(self, workflow_name: str) -> dict[str, Any]:
        """Enable scheduling for a workflow.

        Args:
            workflow_name: Name of the workflow to enable.

        Returns:
            Dictionary with job_id and next_run time.

        Raises:
            ScheduleManagerError: If workflow has no schedulable triggers.
        """
        workflow, path = self._load_workflow(workflow_name)

        # Find schedulable triggers (cron, interval)
        schedulable = [t for t in workflow.triggers if is_schedulable(t)]

        if not schedulable:
            msg = f"Workflow '{workflow_name}' has no schedulable triggers (cron or interval)"
            raise ScheduleManagerError(msg)

        # Use the first schedulable trigger
        trigger_config = schedulable[0]
        ap_trigger = parse_trigger(trigger_config)

        # Schedule with APScheduler
        job_id = self._scheduler.schedule_workflow(
            workflow,
            ap_trigger,
            workflow_path=str(path),
        )

        # Update database
        next_run = self._scheduler.get_next_run(workflow_name)

        with self._db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = repo.get_by_workflow(workflow_name)

            if schedule is None:
                schedule = Schedule(
                    workflow_name=workflow_name,
                    workflow_path=str(path),
                    enabled=1,
                    trigger_config=trigger_config.model_dump(),
                    next_run=next_run,
                )
                repo.create(schedule)
            else:
                schedule.enabled = 1
                schedule.workflow_path = str(path)
                schedule.trigger_config = trigger_config.model_dump()
                schedule.next_run = next_run
                schedule.updated_at = datetime.now(UTC)
                repo.update(schedule)

        logger.info(f"Enabled schedule for workflow: {workflow_name}")

        return {
            "job_id": job_id,
            "workflow_name": workflow_name,
            "next_run": next_run,
            "trigger": str(ap_trigger),
        }

    def disable_workflow(self, workflow_name: str) -> bool:
        """Disable scheduling for a workflow.

        Args:
            workflow_name: Name of the workflow to disable.

        Returns:
            True if disabled, False if not found.
        """
        removed = self._scheduler.remove_schedule(workflow_name)

        with self._db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = repo.get_by_workflow(workflow_name)

            if schedule:
                schedule.enabled = 0
                schedule.next_run = None
                schedule.updated_at = datetime.now(UTC)
                repo.update(schedule)

        if removed:
            logger.info(f"Disabled schedule for workflow: {workflow_name}")

        return removed

    def pause_workflow(self, workflow_name: str) -> bool:
        """Pause a workflow schedule without removing it.

        Args:
            workflow_name: Name of the workflow to pause.

        Returns:
            True if paused, False if not found.
        """
        paused = self._scheduler.pause_schedule(workflow_name)

        if paused:
            with self._db.session_scope() as session:
                repo = ScheduleRepository(session)
                schedule = repo.get_by_workflow(workflow_name)

                if schedule:
                    schedule.next_run = None
                    schedule.updated_at = datetime.now(UTC)
                    repo.update(schedule)

            logger.info(f"Paused schedule for workflow: {workflow_name}")

        return paused

    def resume_workflow(self, workflow_name: str) -> bool:
        """Resume a paused workflow schedule.

        Args:
            workflow_name: Name of the workflow to resume.

        Returns:
            True if resumed, False if not found.
        """
        resumed = self._scheduler.resume_schedule(workflow_name)

        if resumed:
            next_run = self._scheduler.get_next_run(workflow_name)

            with self._db.session_scope() as session:
                repo = ScheduleRepository(session)
                schedule = repo.get_by_workflow(workflow_name)

                if schedule:
                    schedule.next_run = next_run
                    schedule.updated_at = datetime.now(UTC)
                    repo.update(schedule)

            logger.info(f"Resumed schedule for workflow: {workflow_name}")

        return resumed

    def get_status(self, workflow_name: str | None = None) -> list[dict[str, Any]]:
        """Get status of schedules.

        Args:
            workflow_name: Optional specific workflow to get status for.

        Returns:
            List of schedule status dictionaries.
        """
        if workflow_name:
            # Get status for specific workflow
            schedule_info = self._scheduler.get_schedule(workflow_name)

            with self._db.session_scope() as session:
                repo = ScheduleRepository(session)
                db_schedule = repo.get_by_workflow(workflow_name)

                if schedule_info:
                    return [
                        {
                            "name": workflow_name,
                            "enabled": not schedule_info["paused"],
                            "next_run": schedule_info["next_run"],
                            "trigger": schedule_info["trigger"],
                            "last_run": db_schedule.last_run if db_schedule else None,
                            "last_status": db_schedule.last_status if db_schedule else None,
                        }
                    ]
                elif db_schedule:
                    # Schedule exists in DB but not in scheduler (disabled)
                    return [
                        {
                            "name": workflow_name,
                            "enabled": bool(db_schedule.enabled),
                            "next_run": db_schedule.next_run,
                            "trigger": str(db_schedule.trigger_config)
                            if db_schedule.trigger_config
                            else None,
                            "last_run": db_schedule.last_run,
                            "last_status": db_schedule.last_status,
                        }
                    ]
                else:
                    return []

        # Get all schedules
        active_schedules = self._scheduler.get_schedules()

        with self._db.session_scope() as session:
            repo = ScheduleRepository(session)
            all_db_schedules = {s.workflow_name: s for s in repo.get_all()}

            result: list[dict[str, Any]] = []

            # Add active schedules from APScheduler
            seen_names: set[str] = set()
            for sched in active_schedules:
                name = sched["name"]
                seen_names.add(name)
                db_sched = all_db_schedules.get(name)

                result.append(
                    {
                        "name": name,
                        "enabled": not sched["paused"],
                        "next_run": sched["next_run"],
                        "trigger": sched["trigger"],
                        "last_run": db_sched.last_run if db_sched else None,
                        "last_status": db_sched.last_status if db_sched else None,
                    }
                )

            # Add disabled schedules from database
            for name, db_sched in all_db_schedules.items():
                if name not in seen_names:
                    result.append(
                        {
                            "name": name,
                            "enabled": False,
                            "next_run": None,
                            "trigger": str(db_sched.trigger_config)
                            if db_sched.trigger_config
                            else None,
                            "last_run": db_sched.last_run,
                            "last_status": db_sched.last_status,
                        }
                    )

            return result

    def update_last_run(
        self,
        workflow_name: str,
        status: str,
        run_time: datetime | None = None,
    ) -> None:
        """Update last run information for a workflow.

        Args:
            workflow_name: Name of the workflow.
            status: Status of the last run (success, failed, etc.).
            run_time: Time of the run (defaults to now).
        """
        with self._db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = repo.get_by_workflow(workflow_name)

            if schedule:
                schedule.last_run = run_time or datetime.now(UTC)
                schedule.last_status = status
                schedule.next_run = self._scheduler.get_next_run(workflow_name)
                schedule.updated_at = datetime.now(UTC)
                repo.update(schedule)

"""High-level schedule management for FlowPilot workflows."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeGuard

from flowpilot.engine.parser import WorkflowParser
from flowpilot.storage import Database, Schedule, ScheduleRepository

from .file_watcher import FileWatchService  # noqa: TC001
from .service import SchedulerService  # noqa: TC001
from .triggers import is_schedulable, parse_trigger

if TYPE_CHECKING:
    from flowpilot.api.webhooks import WebhookService
    from flowpilot.models import Workflow
    from flowpilot.models.triggers import FileWatchTrigger, WebhookTrigger

logger = logging.getLogger(__name__)


def _is_file_watch_trigger(trigger: Any) -> TypeGuard[FileWatchTrigger]:
    """Check if trigger is a file-watch trigger.

    Args:
        trigger: The trigger to check.

    Returns:
        True if file-watch trigger, False otherwise.
    """
    return getattr(trigger, "type", None) == "file-watch"


def _is_webhook_trigger(trigger: Any) -> TypeGuard[WebhookTrigger]:
    """Check if trigger is a webhook trigger.

    Args:
        trigger: The trigger to check.

    Returns:
        True if webhook trigger, False otherwise.
    """
    return getattr(trigger, "type", None) == "webhook"


class ScheduleManagerError(Exception):
    """Error in schedule management."""


class ScheduleManager:
    """High-level interface for managing workflow schedules.

    Coordinates between the APScheduler service, file watcher service,
    webhook service, and the database for persistent schedule management.
    """

    def __init__(
        self,
        scheduler: SchedulerService,
        db: Database,
        file_watcher: FileWatchService | None = None,
        webhook_service: WebhookService | None = None,
        workflows_dir: Path | None = None,
    ) -> None:
        """Initialize the schedule manager.

        Args:
            scheduler: APScheduler service instance.
            db: Database for schedule persistence.
            file_watcher: Optional file watch service instance.
            webhook_service: Optional webhook service instance.
            workflows_dir: Directory containing workflow files.
        """
        self._scheduler = scheduler
        self._db = db
        self._file_watcher = file_watcher
        self._webhook_service = webhook_service
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
            Dictionary with scheduling results for all trigger types.

        Raises:
            ScheduleManagerError: If workflow has no schedulable triggers.
        """
        workflow, path = self._load_workflow(workflow_name)

        # Find all trigger types
        schedulable = [t for t in workflow.triggers if is_schedulable(t)]
        file_watches = [t for t in workflow.triggers if _is_file_watch_trigger(t)]
        webhooks = [t for t in workflow.triggers if _is_webhook_trigger(t)]

        if not schedulable and not file_watches and not webhooks:
            msg = (
                f"Workflow '{workflow_name}' has no schedulable triggers "
                "(cron, interval, file-watch, or webhook)"
            )
            raise ScheduleManagerError(msg)

        result: dict[str, Any] = {
            "workflow_name": workflow_name,
            "scheduled": [],
            "file_watches": [],
            "webhooks": [],
        }

        # Schedule cron/interval triggers with APScheduler
        trigger_config = None
        next_run = None
        if schedulable:
            trigger_config = schedulable[0]
            ap_trigger = parse_trigger(trigger_config)

            job_id = self._scheduler.schedule_workflow(
                workflow,
                ap_trigger,
                workflow_path=str(path),
            )

            next_run = self._scheduler.get_next_run(workflow_name)
            result["scheduled"].append(
                {
                    "type": trigger_config.type,
                    "job_id": job_id,
                    "next_run": next_run,
                    "trigger": str(ap_trigger),
                }
            )

        # Add file watches
        if file_watches and self._file_watcher:
            for fw_trigger in file_watches:
                watch_id = self._file_watcher.add_watch(
                    workflow_name,
                    fw_trigger,
                    str(path),
                )
                result["file_watches"].append(
                    {
                        "watch_id": watch_id,
                        "path": fw_trigger.path,
                        "events": fw_trigger.events,
                        "pattern": fw_trigger.pattern,
                    }
                )

        # Register webhooks
        if webhooks and self._webhook_service:
            for wh_trigger in webhooks:
                webhook_id = self._webhook_service.register(
                    workflow_name,
                    wh_trigger,
                    str(path),
                )
                result["webhooks"].append(
                    {
                        "webhook_id": webhook_id,
                        "path": wh_trigger.path,
                        "has_secret": wh_trigger.secret is not None,
                    }
                )

        # Update database
        with self._db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = repo.get_by_workflow(workflow_name)

            # Build combined trigger config for storage
            combined_config: dict[str, Any] = {}
            if trigger_config:
                combined_config["schedule"] = trigger_config.model_dump()
            if file_watches:
                combined_config["file_watches"] = [fw.model_dump() for fw in file_watches]
            if webhooks:
                combined_config["webhooks"] = [wh.model_dump() for wh in webhooks]

            if schedule is None:
                schedule = Schedule(
                    workflow_name=workflow_name,
                    workflow_path=str(path),
                    enabled=1,
                    trigger_config=combined_config,
                    next_run=next_run,
                )
                repo.create(schedule)
            else:
                schedule.enabled = 1
                schedule.workflow_path = str(path)
                schedule.trigger_config = combined_config
                schedule.next_run = next_run
                schedule.updated_at = datetime.now(UTC)
                repo.update(schedule)

        logger.info(f"Enabled schedule for workflow: {workflow_name}")

        return result

    def disable_workflow(self, workflow_name: str) -> dict[str, Any]:
        """Disable scheduling for a workflow.

        Args:
            workflow_name: Name of the workflow to disable.

        Returns:
            Dictionary with disabled trigger info.
        """
        result: dict[str, Any] = {
            "workflow_name": workflow_name,
            "schedule_removed": False,
            "file_watch_removed": False,
            "webhook_removed": False,
        }

        # Remove APScheduler job
        result["schedule_removed"] = self._scheduler.remove_schedule(workflow_name)

        # Remove file watch
        if self._file_watcher:
            result["file_watch_removed"] = self._file_watcher.remove_watch(workflow_name)

        # Remove webhook
        if self._webhook_service:
            result["webhook_removed"] = self._webhook_service.unregister(workflow_name)

        # Update database
        with self._db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = repo.get_by_workflow(workflow_name)

            if schedule:
                schedule.enabled = 0
                schedule.next_run = None
                schedule.updated_at = datetime.now(UTC)
                repo.update(schedule)

        if result["schedule_removed"] or result["file_watch_removed"] or result["webhook_removed"]:
            logger.info(f"Disabled schedule for workflow: {workflow_name}")

        return result

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
        # Get active file watches
        file_watches = {}
        if self._file_watcher:
            for watch in self._file_watcher.get_watches():
                file_watches[watch["workflow"]] = watch

        # Get active webhooks
        webhooks = {}
        if self._webhook_service:
            for webhook in self._webhook_service.get_webhooks():
                webhooks[webhook["workflow_name"]] = webhook

        if workflow_name:
            # Get status for specific workflow
            schedule_info = self._scheduler.get_schedule(workflow_name)
            file_watch_info = file_watches.get(workflow_name)
            webhook_info = webhooks.get(workflow_name)

            with self._db.session_scope() as session:
                repo = ScheduleRepository(session)
                db_schedule = repo.get_by_workflow(workflow_name)

                if schedule_info or file_watch_info or webhook_info:
                    return [
                        {
                            "name": workflow_name,
                            "enabled": True,
                            "next_run": schedule_info["next_run"] if schedule_info else None,
                            "trigger": schedule_info["trigger"] if schedule_info else None,
                            "file_watch": file_watch_info,
                            "webhook": webhook_info,
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
                            "file_watch": None,
                            "webhook": None,
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
                        "file_watch": file_watches.get(name),
                        "webhook": webhooks.get(name),
                        "last_run": db_sched.last_run if db_sched else None,
                        "last_status": db_sched.last_status if db_sched else None,
                    }
                )

            # Add workflows with only file watches (no APScheduler job)
            for name, watch_info in file_watches.items():
                if name not in seen_names:
                    seen_names.add(name)
                    db_sched = all_db_schedules.get(name)
                    result.append(
                        {
                            "name": name,
                            "enabled": True,
                            "next_run": None,
                            "trigger": None,
                            "file_watch": watch_info,
                            "webhook": webhooks.get(name),
                            "last_run": db_sched.last_run if db_sched else None,
                            "last_status": db_sched.last_status if db_sched else None,
                        }
                    )

            # Add workflows with only webhooks (no APScheduler job or file watch)
            for name, webhook_info in webhooks.items():
                if name not in seen_names:
                    seen_names.add(name)
                    db_sched = all_db_schedules.get(name)
                    result.append(
                        {
                            "name": name,
                            "enabled": True,
                            "next_run": None,
                            "trigger": None,
                            "file_watch": None,
                            "webhook": webhook_info,
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
                            "file_watch": None,
                            "webhook": None,
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

"""Tests for SchedulerService."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from apscheduler.triggers.cron import CronTrigger as APCronTrigger
from apscheduler.triggers.interval import IntervalTrigger as APIntervalTrigger

from flowpilot.models import Workflow
from flowpilot.models.triggers import ManualTrigger
from flowpilot.scheduler.service import SchedulerService


@pytest.fixture
def scheduler_service(tmp_path: Path) -> SchedulerService:
    """Create a SchedulerService with in-memory database."""
    db_url = f"sqlite:///{tmp_path / 'scheduler.db'}"
    return SchedulerService(db_url, tmp_path / "workflows")


@pytest.fixture
def sample_workflow() -> Workflow:
    """Create a sample workflow for testing."""
    return Workflow(
        name="test-workflow",
        triggers=[ManualTrigger(type="manual")],
        nodes=[
            {"id": "step-1", "type": "shell", "command": "echo hello"},
        ],
    )


class TestSchedulerService:
    """Tests for SchedulerService class."""

    def test_init(self, scheduler_service: SchedulerService) -> None:
        """Test service initialization."""
        assert scheduler_service.is_running is False

    def test_start_stop(self, scheduler_service: SchedulerService) -> None:
        """Test starting and stopping the scheduler."""
        scheduler_service.start()
        assert scheduler_service.is_running is True

        scheduler_service.shutdown()
        assert scheduler_service.is_running is False

    def test_start_idempotent(self, scheduler_service: SchedulerService) -> None:
        """Test that start is idempotent."""
        scheduler_service.start()
        scheduler_service.start()  # Should not raise
        assert scheduler_service.is_running is True
        scheduler_service.shutdown()

    def test_shutdown_idempotent(self, scheduler_service: SchedulerService) -> None:
        """Test that shutdown is idempotent."""
        scheduler_service.shutdown()  # Should not raise
        assert scheduler_service.is_running is False

    def test_schedule_workflow_cron(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test scheduling a workflow with cron trigger."""
        scheduler_service.start()

        try:
            trigger = APCronTrigger(hour=9, minute=0)
            job_id = scheduler_service.schedule_workflow(sample_workflow, trigger)

            assert job_id == f"workflow:{sample_workflow.name}"

            # Verify job exists
            schedules = scheduler_service.get_schedules()
            assert len(schedules) == 1
            assert schedules[0]["name"] == sample_workflow.name

        finally:
            scheduler_service.shutdown()

    def test_schedule_workflow_interval(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test scheduling a workflow with interval trigger."""
        scheduler_service.start()

        try:
            trigger = APIntervalTrigger(minutes=5)
            job_id = scheduler_service.schedule_workflow(sample_workflow, trigger)

            assert job_id == f"workflow:{sample_workflow.name}"

            # Verify job exists
            schedules = scheduler_service.get_schedules()
            assert len(schedules) == 1

        finally:
            scheduler_service.shutdown()

    def test_schedule_workflow_replace_existing(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test that scheduling replaces existing schedule."""
        scheduler_service.start()

        try:
            # Schedule with cron
            trigger1 = APCronTrigger(hour=9, minute=0)
            scheduler_service.schedule_workflow(sample_workflow, trigger1)

            # Schedule with interval (should replace)
            trigger2 = APIntervalTrigger(minutes=5)
            scheduler_service.schedule_workflow(sample_workflow, trigger2)

            # Verify only one job exists
            schedules = scheduler_service.get_schedules()
            assert len(schedules) == 1
            assert "interval" in schedules[0]["trigger"].lower()

        finally:
            scheduler_service.shutdown()

    def test_remove_schedule(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test removing a workflow schedule."""
        scheduler_service.start()

        try:
            trigger = APCronTrigger(hour=9, minute=0)
            scheduler_service.schedule_workflow(sample_workflow, trigger)

            # Remove
            result = scheduler_service.remove_schedule(sample_workflow.name)
            assert result is True

            # Verify removed
            schedules = scheduler_service.get_schedules()
            assert len(schedules) == 0

        finally:
            scheduler_service.shutdown()

    def test_remove_nonexistent_schedule(
        self,
        scheduler_service: SchedulerService,
    ) -> None:
        """Test removing a non-existent schedule returns False."""
        scheduler_service.start()

        try:
            result = scheduler_service.remove_schedule("nonexistent")
            assert result is False

        finally:
            scheduler_service.shutdown()

    def test_pause_resume_schedule(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test pausing and resuming a schedule."""
        scheduler_service.start()

        try:
            trigger = APCronTrigger(hour=9, minute=0)
            scheduler_service.schedule_workflow(sample_workflow, trigger)

            # Pause
            result = scheduler_service.pause_schedule(sample_workflow.name)
            assert result is True

            # Verify paused
            schedules = scheduler_service.get_schedules()
            assert schedules[0]["paused"] is True

            # Resume
            result = scheduler_service.resume_schedule(sample_workflow.name)
            assert result is True

            # Verify resumed
            schedules = scheduler_service.get_schedules()
            assert schedules[0]["paused"] is False

        finally:
            scheduler_service.shutdown()

    def test_get_schedule(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test getting schedule for a specific workflow."""
        scheduler_service.start()

        try:
            trigger = APCronTrigger(hour=9, minute=0)
            scheduler_service.schedule_workflow(sample_workflow, trigger)

            schedule = scheduler_service.get_schedule(sample_workflow.name)
            assert schedule is not None
            assert schedule["name"] == sample_workflow.name
            assert schedule["next_run"] is not None

        finally:
            scheduler_service.shutdown()

    def test_get_schedule_nonexistent(
        self,
        scheduler_service: SchedulerService,
    ) -> None:
        """Test getting schedule for non-existent workflow."""
        scheduler_service.start()

        try:
            schedule = scheduler_service.get_schedule("nonexistent")
            assert schedule is None

        finally:
            scheduler_service.shutdown()

    def test_get_next_run(
        self,
        scheduler_service: SchedulerService,
        sample_workflow: Workflow,
    ) -> None:
        """Test getting next run time."""
        scheduler_service.start()

        try:
            trigger = APCronTrigger(hour=9, minute=0)
            scheduler_service.schedule_workflow(sample_workflow, trigger)

            next_run = scheduler_service.get_next_run(sample_workflow.name)
            assert next_run is not None

        finally:
            scheduler_service.shutdown()

    def test_get_next_run_nonexistent(
        self,
        scheduler_service: SchedulerService,
    ) -> None:
        """Test getting next run for non-existent workflow."""
        scheduler_service.start()

        try:
            next_run = scheduler_service.get_next_run("nonexistent")
            assert next_run is None

        finally:
            scheduler_service.shutdown()

    def test_set_runner(
        self,
        scheduler_service: SchedulerService,
    ) -> None:
        """Test setting the workflow runner."""
        mock_runner = MagicMock()
        scheduler_service.set_runner(mock_runner)
        assert scheduler_service._runner == mock_runner

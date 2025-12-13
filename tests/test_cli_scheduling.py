"""Tests for CLI scheduling commands."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from flowpilot.cli import app
from flowpilot.storage import (
    Database,
    Execution,
    ExecutionRepository,
    ExecutionStatus,
    NodeExecution,
    NodeExecutionRepository,
)


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database with test data."""
    db_path = tmp_path / ".flowpilot" / "flowpilot.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = Database(db_path)
    db.create_tables()

    # Add test executions
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        node_repo = NodeExecutionRepository(session)

        # Create successful execution
        exec1 = Execution(
            id="exec-001-aaaa-bbbb-cccc",
            workflow_name="test-workflow",
            workflow_path="/path/to/workflow.yaml",
            status=ExecutionStatus.SUCCESS,
            trigger_type="manual",
            started_at=datetime.now() - timedelta(hours=1),
            finished_at=datetime.now() - timedelta(minutes=59),
            duration_ms=60000,
        )
        repo.create(exec1)

        # Add node execution for exec1
        node1 = NodeExecution(
            execution_id="exec-001-aaaa-bbbb-cccc",
            node_id="shell-node",
            node_type="shell",
            status="success",
            started_at=datetime.now() - timedelta(hours=1),
            finished_at=datetime.now() - timedelta(minutes=59),
            duration_ms=60000,
            stdout="Hello from shell\nOutput line 2",
            stderr="",
            output="",
        )
        node_repo.create(node1)

        # Create failed execution
        exec2 = Execution(
            id="exec-002-dddd-eeee-ffff",
            workflow_name="test-workflow",
            workflow_path="/path/to/workflow.yaml",
            status=ExecutionStatus.FAILED,
            trigger_type="cron",
            started_at=datetime.now() - timedelta(minutes=30),
            finished_at=datetime.now() - timedelta(minutes=29),
            duration_ms=60000,
            error="Node failed: shell error",
        )
        repo.create(exec2)

        # Add node execution for exec2
        node2 = NodeExecution(
            execution_id="exec-002-dddd-eeee-ffff",
            node_id="failing-node",
            node_type="shell",
            status="error",
            started_at=datetime.now() - timedelta(minutes=30),
            finished_at=datetime.now() - timedelta(minutes=29),
            duration_ms=60000,
            stderr="Command not found",
            error="Exit code 127",
            stdout="",
            output="",
        )
        node_repo.create(node2)

        # Create another workflow's execution
        exec3 = Execution(
            id="exec-003-gggg-hhhh-iiii",
            workflow_name="other-workflow",
            workflow_path="/path/to/other.yaml",
            status=ExecutionStatus.SUCCESS,
            trigger_type="webhook",
            started_at=datetime.now() - timedelta(minutes=10),
            finished_at=datetime.now() - timedelta(minutes=9),
            duration_ms=60000,
        )
        repo.create(exec3)

    return db_path


class TestHistoryCommand:
    """Tests for history command."""

    def test_history_no_executions(self, runner, tmp_path):
        """Test history command with no executions."""
        db_path = tmp_path / ".flowpilot" / "flowpilot.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = Database(db_path)
        db.create_tables()

        with patch(
            "flowpilot.cli.commands.history.get_flowpilot_dir", return_value=tmp_path / ".flowpilot"
        ):
            result = runner.invoke(app, ["history"])
            assert result.exit_code == 0
            assert "No execution history found" in result.output

    def test_history_with_executions(self, runner, tmp_path, temp_db):
        """Test history command shows executions."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history"])
            assert result.exit_code == 0
            assert "test-workflow" in result.output
            assert "other-workflow" in result.output

    def test_history_filter_by_workflow(self, runner, tmp_path, temp_db):
        """Test history command filters by workflow name."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "test-workflow"])
            assert result.exit_code == 0
            assert "test-workflow" in result.output
            assert "other-workflow" not in result.output

    def test_history_filter_by_status(self, runner, tmp_path, temp_db):
        """Test history command filters by status."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "--status", "failed"])
            assert result.exit_code == 0
            assert "failed" in result.output.lower()

    def test_history_json_output(self, runner, tmp_path, temp_db):
        """Test history command with JSON output."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "--json"])
            assert result.exit_code == 0
            # Should contain JSON array
            assert "[" in result.output
            assert "workflow_name" in result.output

    def test_history_with_id(self, runner, tmp_path, temp_db):
        """Test history command with specific execution ID."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "--id", "exec-001"])
            assert result.exit_code == 0
            assert "test-workflow" in result.output
            assert "shell-node" in result.output

    def test_history_with_last_flag(self, runner, tmp_path, temp_db):
        """Test history command with --last flag."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "--last"])
            assert result.exit_code == 0
            # Should show execution details
            assert "Execution:" in result.output

    def test_history_with_last_flag_for_workflow(self, runner, tmp_path, temp_db):
        """Test history command with --last flag for specific workflow."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "test-workflow", "--last"])
            assert result.exit_code == 0
            assert "test-workflow" in result.output

    def test_history_invalid_status(self, runner, tmp_path, temp_db):
        """Test history command with invalid status filter."""
        with patch("flowpilot.cli.commands.history.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["history", "--status", "invalid"])
            assert result.exit_code == 1
            assert "Invalid status" in result.output


class TestLogsCommand:
    """Tests for logs command."""

    def test_logs_no_executions(self, runner, tmp_path):
        """Test logs command with no executions."""
        db_path = tmp_path / ".flowpilot" / "flowpilot.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        db = Database(db_path)
        db.create_tables()

        with patch(
            "flowpilot.cli.commands.logs.get_flowpilot_dir", return_value=tmp_path / ".flowpilot"
        ):
            result = runner.invoke(app, ["logs", "nonexistent"])
            assert result.exit_code == 0
            assert "No executions found" in result.output

    def test_logs_shows_workflow_logs(self, runner, tmp_path, temp_db):
        """Test logs command shows workflow execution logs."""
        with patch("flowpilot.cli.commands.logs.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["logs", "test-workflow"])
            assert result.exit_code == 0
            assert "test-workflow" in result.output
            # Should show node outputs
            assert "shell-node" in result.output or "failing-node" in result.output

    def test_logs_with_lines_limit(self, runner, tmp_path, temp_db):
        """Test logs command with custom line limit."""
        with patch("flowpilot.cli.commands.logs.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["logs", "test-workflow", "-n", "1"])
            assert result.exit_code == 0

    def test_logs_with_execution_id(self, runner, tmp_path, temp_db):
        """Test logs command with specific execution ID."""
        with patch("flowpilot.cli.commands.logs.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["logs", "test-workflow", "-e", "exec-001"])
            assert result.exit_code == 0
            assert "exec-001" in result.output

    def test_logs_nonexistent_execution(self, runner, tmp_path, temp_db):
        """Test logs command with non-existent execution ID."""
        with patch("flowpilot.cli.commands.logs.get_flowpilot_dir", return_value=temp_db.parent):
            result = runner.invoke(app, ["logs", "test-workflow", "-e", "nonexistent"])
            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_logs_not_initialized(self, runner, tmp_path):
        """Test logs command when FlowPilot not initialized."""
        with patch(
            "flowpilot.cli.commands.logs.get_flowpilot_dir", return_value=tmp_path / ".flowpilot"
        ):
            result = runner.invoke(app, ["logs", "test"])
            assert result.exit_code == 0
            assert "No execution history" in result.output


class TestScheduleCommands:
    """Tests for schedule commands (enable/disable/status)."""

    def test_enable_not_initialized(self, runner, tmp_path):
        """Test enable command when FlowPilot not initialized."""
        with patch(
            "flowpilot.cli.commands.schedule.get_flowpilot_dir",
            return_value=tmp_path / ".flowpilot",
        ):
            result = runner.invoke(app, ["enable", "test"])
            assert result.exit_code == 1
            assert "not initialized" in result.output.lower()

    def test_disable_not_initialized(self, runner, tmp_path):
        """Test disable command when FlowPilot not initialized."""
        with patch(
            "flowpilot.cli.commands.schedule.get_flowpilot_dir",
            return_value=tmp_path / ".flowpilot",
        ):
            result = runner.invoke(app, ["disable", "test"])
            assert result.exit_code == 1
            assert "not initialized" in result.output.lower()

    def test_status_not_initialized(self, runner, tmp_path):
        """Test status command when FlowPilot not initialized."""
        with patch(
            "flowpilot.cli.commands.schedule.get_flowpilot_dir",
            return_value=tmp_path / ".flowpilot",
        ):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 1
            assert "not initialized" in result.output.lower()

    def test_enable_with_mock_manager(self, runner, tmp_path, temp_db):
        """Test enable command with mocked schedule manager."""
        mock_manager = MagicMock()
        mock_manager.enable_workflow.return_value = {
            "scheduled": [{"trigger": "cron: 0 * * * *", "next_run": datetime.now()}],
            "file_watches": [],
            "webhooks": [],
        }

        with (
            patch("flowpilot.cli.commands.schedule.get_flowpilot_dir", return_value=temp_db.parent),
            patch(
                "flowpilot.cli.commands.schedule._get_schedule_manager", return_value=mock_manager
            ),
        ):
            result = runner.invoke(app, ["enable", "test-workflow"])
            assert result.exit_code == 0
            assert "Enabled" in result.output
            mock_manager.enable_workflow.assert_called_once_with("test-workflow")

    def test_disable_with_mock_manager(self, runner, tmp_path, temp_db):
        """Test disable command with mocked schedule manager."""
        mock_manager = MagicMock()
        mock_manager.disable_workflow.return_value = {
            "schedule_removed": True,
            "file_watch_removed": False,
            "webhook_removed": False,
        }

        with (
            patch("flowpilot.cli.commands.schedule.get_flowpilot_dir", return_value=temp_db.parent),
            patch(
                "flowpilot.cli.commands.schedule._get_schedule_manager", return_value=mock_manager
            ),
        ):
            result = runner.invoke(app, ["disable", "test-workflow"])
            assert result.exit_code == 0
            assert "Disabled" in result.output
            mock_manager.disable_workflow.assert_called_once_with("test-workflow")

    def test_status_empty(self, runner, tmp_path, temp_db):
        """Test status command with no schedules."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = []

        with (
            patch("flowpilot.cli.commands.schedule.get_flowpilot_dir", return_value=temp_db.parent),
            patch(
                "flowpilot.cli.commands.schedule._get_schedule_manager", return_value=mock_manager
            ),
        ):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            assert "No scheduled" in result.output

    def test_status_with_schedules(self, runner, tmp_path, temp_db):
        """Test status command with active schedules."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = [
            {
                "name": "test-workflow",
                "enabled": True,
                "next_run": datetime.now() + timedelta(hours=1),
                "trigger": "cron: 0 * * * *",
                "file_watch": None,
                "webhook": None,
                "last_run": datetime.now() - timedelta(hours=1),
                "last_status": "success",
            }
        ]

        with (
            patch("flowpilot.cli.commands.schedule.get_flowpilot_dir", return_value=temp_db.parent),
            patch(
                "flowpilot.cli.commands.schedule._get_schedule_manager", return_value=mock_manager
            ),
        ):
            result = runner.invoke(app, ["status"])
            assert result.exit_code == 0
            # Name may be truncated in table output
            assert "test-workf" in result.output or "test-workflow" in result.output

    def test_status_json_output(self, runner, tmp_path, temp_db):
        """Test status command with JSON output."""
        mock_manager = MagicMock()
        mock_manager.get_status.return_value = [
            {
                "name": "test-workflow",
                "enabled": True,
                "next_run": datetime.now() + timedelta(hours=1),
                "trigger": "cron: 0 * * * *",
                "file_watch": None,
                "webhook": None,
                "last_run": datetime.now() - timedelta(hours=1),
                "last_status": "success",
            }
        ]

        with (
            patch("flowpilot.cli.commands.schedule.get_flowpilot_dir", return_value=temp_db.parent),
            patch(
                "flowpilot.cli.commands.schedule._get_schedule_manager", return_value=mock_manager
            ),
        ):
            result = runner.invoke(app, ["status", "--json"])
            assert result.exit_code == 0
            assert "[" in result.output  # JSON array
            assert "test-workflow" in result.output

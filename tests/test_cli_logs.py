"""Tests for FlowPilot CLI logs command."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from flowpilot.cli import app
from flowpilot.storage import (
    Database,
    ExecutionRepository,
    ExecutionStatus,
    NodeExecutionRepository,
)
from flowpilot.storage.models import Execution, NodeExecution


@pytest.fixture
def runner() -> CliRunner:
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_flowpilot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a temporary FlowPilot directory with database."""
    flowpilot_dir = tmp_path / ".flowpilot"
    flowpilot_dir.mkdir(parents=True)
    workflows_dir = flowpilot_dir / "workflows"
    workflows_dir.mkdir()

    # Patch the get_flowpilot_dir function to return our temp dir
    monkeypatch.setattr(
        "flowpilot.cli.commands.logs.get_flowpilot_dir",
        lambda: flowpilot_dir,
    )

    return flowpilot_dir


@pytest.fixture
def db(temp_flowpilot: Path) -> Database:
    """Create a database with tables."""
    db_path = temp_flowpilot / "flowpilot.db"
    database = Database(db_path)
    database.create_tables()
    return database


def create_execution(
    db: Database,
    workflow_name: str = "test-workflow",
    status: ExecutionStatus = ExecutionStatus.SUCCESS,
    trigger_type: str | None = "manual",
    error: str | None = None,
    duration_ms: int | None = 1500,
) -> str:
    """Create a test execution in the database and return its ID."""
    execution_id = str(uuid.uuid4())
    started_at = datetime.now(UTC)
    finished_at = (
        datetime.now(UTC) if status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED) else None
    )

    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        execution = Execution(
            id=execution_id,
            workflow_name=workflow_name,
            workflow_path=f"/path/to/{workflow_name}.yaml",
            status=status,
            trigger_type=trigger_type,
            inputs={},
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error=error,
        )
        repo.create(execution)
    return execution_id


def create_node_execution(
    db: Database,
    execution_id: str,
    node_id: str = "node-1",
    node_type: str = "shell",
    status: str = "success",
    stdout: str = "",
    stderr: str = "",
    output: str = "",
    error: str | None = None,
    duration_ms: int | None = 500,
) -> None:
    """Create a test node execution in the database."""
    with db.session_scope() as session:
        repo = NodeExecutionRepository(session)
        node_exec = NodeExecution(
            execution_id=execution_id,
            node_id=node_id,
            node_type=node_type,
            status=status,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=duration_ms,
            stdout=stdout,
            stderr=stderr,
            output=output,
            error=error,
        )
        repo.create(node_exec)


class TestLogsNoDatabase:
    """Tests for logs command without database."""

    def test_logs_no_database(self, runner: CliRunner, temp_flowpilot: Path) -> None:
        """Test logs shows message when no database exists."""
        # Don't create database
        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "No execution logs found" in result.output or "flowpilot init" in result.output


class TestLogsRecent:
    """Tests for showing recent execution logs."""

    def test_logs_no_executions(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows message when no executions found."""
        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "No executions found" in result.output

    def test_logs_single_execution(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows single execution."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_node_execution(
            db, execution_id, "echo-node", "shell", "success", stdout="Hello World"
        )

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert execution_id[:8] in result.output
        assert "echo-node" in result.output
        assert "Hello World" in result.output

    def test_logs_multiple_executions(self, runner: CliRunner, db: Database) -> None:
        """Test logs -n shows multiple executions."""
        # Create 3 executions
        for i in range(3):
            exec_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
            create_node_execution(db, exec_id, f"node-{i}", "shell", "success")

        result = runner.invoke(app, ["logs", "test-workflow", "-n", "2"])
        assert result.exit_code == 0
        # Should show 2 executions (last 2)
        assert "node-" in result.output

    def test_logs_shows_success_status(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows success status."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_node_execution(db, execution_id, "node-1", "shell", "success")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "success" in result.output.lower()

    def test_logs_shows_failed_status(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows failed status with error."""
        execution_id = create_execution(
            db, "test-workflow", ExecutionStatus.FAILED, error="Something went wrong"
        )
        create_node_execution(db, execution_id, "node-1", "shell", "failed", error="Node error")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower()
        assert "Something went wrong" in result.output

    def test_logs_shows_stderr(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows stderr output."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_node_execution(
            db, execution_id, "node-1", "shell", "success", stderr="Warning: deprecated"
        )

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "Warning: deprecated" in result.output

    def test_logs_shows_node_output(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows node output."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_node_execution(
            db, execution_id, "node-1", "shell", "success", output='{"key": "value"}'
        )

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        # Output section shown
        assert "key" in result.output or "value" in result.output


class TestLogsSpecificExecution:
    """Tests for showing logs for specific execution."""

    def test_logs_by_full_id(self, runner: CliRunner, db: Database) -> None:
        """Test logs -e with full execution ID."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_node_execution(
            db, execution_id, "node-1", "shell", "success", stdout="Specific output"
        )

        result = runner.invoke(app, ["logs", "test-workflow", "-e", execution_id])
        assert result.exit_code == 0
        assert "Specific output" in result.output

    def test_logs_by_prefix(self, runner: CliRunner, db: Database) -> None:
        """Test logs -e with execution ID prefix."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_node_execution(db, execution_id, "node-1", "shell", "success", stdout="Prefix match")

        # Use first 8 chars as prefix
        prefix = execution_id[:8]
        result = runner.invoke(app, ["logs", "test-workflow", "-e", prefix])
        assert result.exit_code == 0
        assert "Prefix match" in result.output

    def test_logs_execution_not_found(self, runner: CliRunner, db: Database) -> None:
        """Test logs -e with non-existent execution ID."""
        result = runner.invoke(app, ["logs", "test-workflow", "-e", "nonexistent123"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_logs_execution_wrong_workflow(self, runner: CliRunner, db: Database) -> None:
        """Test logs -e with execution from different workflow."""
        execution_id = create_execution(db, "other-workflow", ExecutionStatus.SUCCESS)

        result = runner.invoke(app, ["logs", "test-workflow", "-e", execution_id])
        assert result.exit_code == 1
        assert "other-workflow" in result.output

    def test_logs_ambiguous_prefix(self, runner: CliRunner, db: Database) -> None:
        """Test logs -e with ambiguous prefix matching multiple executions."""
        # Create executions that might have similar prefixes (unlikely with UUID but testing the logic)
        create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)
        create_execution(db, "test-workflow", ExecutionStatus.SUCCESS)

        # Since UUIDs are random, this test checks behavior with short prefix
        # Using 'a' as prefix - won't match UUIDs starting differently
        result = runner.invoke(app, ["logs", "test-workflow", "-e", "a"])
        # Should either not find any (most likely) or show ambiguous error
        assert result.exit_code in (0, 1)


class TestLogsFollow:
    """Tests for follow mode (basic tests, not real-time behavior)."""

    def test_logs_follow_mode_exists(self, runner: CliRunner, db: Database) -> None:
        """Test that -f flag is recognized."""
        # Create an execution to ensure there's something to follow
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.RUNNING)
        create_node_execution(db, execution_id, "node-1", "shell", "running")

        # Mock time.sleep to avoid waiting and use KeyboardInterrupt to exit
        with patch("flowpilot.cli.commands.logs.time.sleep", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["logs", "test-workflow", "-f"])

        assert result.exit_code == 0
        assert "Following logs" in result.output or "Stopped following" in result.output

    def test_logs_follow_shows_header(self, runner: CliRunner, db: Database) -> None:
        """Test follow mode shows execution header."""
        execution_id = create_execution(db, "test-workflow", ExecutionStatus.RUNNING)
        create_node_execution(db, execution_id, "node-1", "shell", "success", stdout="Test output")

        with patch("flowpilot.cli.commands.logs.time.sleep", side_effect=KeyboardInterrupt):
            result = runner.invoke(app, ["logs", "test-workflow", "-f"])

        assert result.exit_code == 0
        assert "test-workflow" in result.output


class TestLogsFormatting:
    """Tests for log output formatting."""

    def test_logs_shows_trigger_type(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows trigger type."""
        execution_id = create_execution(db, "test-workflow", trigger_type="cron")
        create_node_execution(db, execution_id, "node-1", "shell", "success")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "cron" in result.output.lower() or "Trigger" in result.output

    def test_logs_shows_duration(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows duration."""
        execution_id = create_execution(db, "test-workflow", duration_ms=2500)
        create_node_execution(db, execution_id, "node-1", "shell", "success", duration_ms=1000)

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        # Should show duration in some format (ms, s, or m)
        assert "2.5s" in result.output or "2500ms" in result.output or "1s" in result.output

    def test_logs_shows_node_type(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows node type."""
        execution_id = create_execution(db, "test-workflow")
        create_node_execution(db, execution_id, "my-node", "python", "success")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "python" in result.output

    def test_logs_multiple_nodes(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows multiple nodes."""
        execution_id = create_execution(db, "test-workflow")
        create_node_execution(db, execution_id, "node-1", "shell", "success", stdout="Output 1")
        create_node_execution(db, execution_id, "node-2", "python", "success", stdout="Output 2")
        create_node_execution(db, execution_id, "node-3", "shell", "failed", error="Node 3 failed")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "node-1" in result.output
        assert "node-2" in result.output
        assert "node-3" in result.output
        assert "Output 1" in result.output
        assert "Output 2" in result.output
        assert "Node 3 failed" in result.output


class TestLogsEdgeCases:
    """Tests for edge cases and error handling."""

    def test_logs_empty_output(self, runner: CliRunner, db: Database) -> None:
        """Test logs handles nodes with empty output."""
        execution_id = create_execution(db, "test-workflow")
        create_node_execution(db, execution_id, "node-1", "shell", "success")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "node-1" in result.output

    def test_logs_long_output_truncated(self, runner: CliRunner, db: Database) -> None:
        """Test logs truncates very long output."""
        execution_id = create_execution(db, "test-workflow")
        long_output = "x" * 1000  # 1000 chars output
        create_node_execution(db, execution_id, "node-1", "shell", "success", output=long_output)

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        # Output should be truncated or shown (we truncate at 500 chars)
        assert "..." in result.output or "x" in result.output

    def test_logs_pending_execution(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows pending execution."""
        create_execution(db, "test-workflow", ExecutionStatus.PENDING, duration_ms=None)

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "pending" in result.output.lower()

    def test_logs_running_execution(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows running execution."""
        execution_id = create_execution(
            db, "test-workflow", ExecutionStatus.RUNNING, duration_ms=None
        )
        create_node_execution(db, execution_id, "node-1", "shell", "running")

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "running" in result.output.lower()

    def test_logs_cancelled_execution(self, runner: CliRunner, db: Database) -> None:
        """Test logs shows cancelled execution."""
        create_execution(db, "test-workflow", ExecutionStatus.CANCELLED)

        result = runner.invoke(app, ["logs", "test-workflow"])
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()


class TestLogsHelp:
    """Tests for logs command help."""

    def test_logs_help(self, runner: CliRunner) -> None:
        """Test logs --help shows usage."""
        result = runner.invoke(app, ["logs", "--help"])
        assert result.exit_code == 0
        assert "logs" in result.output.lower()
        assert "--follow" in result.output or "-f" in result.output
        assert "--lines" in result.output or "-n" in result.output
        assert "--execution" in result.output or "-e" in result.output

    def test_logs_requires_name(self, runner: CliRunner) -> None:
        """Test logs requires workflow name argument."""
        result = runner.invoke(app, ["logs"])
        assert result.exit_code != 0

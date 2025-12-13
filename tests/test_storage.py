"""Tests for FlowPilot storage layer."""

from datetime import UTC, datetime, timedelta

import pytest

from flowpilot.storage import (
    Database,
    Execution,
    ExecutionRepository,
    ExecutionStatus,
    NodeExecution,
    NodeExecutionRepository,
    Schedule,
    ScheduleRepository,
)


@pytest.fixture
def db() -> Database:
    """Create an in-memory database for testing."""
    database = Database(":memory:")
    database.create_tables()
    return database


class TestDatabase:
    """Tests for Database class."""

    def test_create_in_memory(self) -> None:
        """Test creating an in-memory database."""
        db = Database(":memory:")
        db.create_tables()
        # Should not raise
        with db.session_scope() as session:
            assert session is not None

    def test_create_file_database(self, tmp_path: pytest.TempPathFactory) -> None:
        """Test creating a file-based database."""
        db_path = tmp_path / "test.db"  # type: ignore[operator]
        db = Database(db_path)
        db.create_tables()

        assert db_path.exists()

    def test_session_scope_commits_on_success(self, db: Database) -> None:
        """Test that session_scope commits on success."""
        with db.session_scope() as session:
            execution = Execution(
                id="test-123",
                workflow_name="test-workflow",
                workflow_path="/test/path",
                status=ExecutionStatus.SUCCESS,
            )
            session.add(execution)

        # Should be committed
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            result = repo.get_by_id("test-123")
            assert result is not None
            assert result.workflow_name == "test-workflow"

    def test_session_scope_rolls_back_on_error(self, db: Database) -> None:
        """Test that session_scope rolls back on error."""
        try:
            with db.session_scope() as session:
                execution = Execution(
                    id="test-456",
                    workflow_name="test-workflow",
                    workflow_path="/test/path",
                    status=ExecutionStatus.SUCCESS,
                )
                session.add(execution)
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should not be committed
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            result = repo.get_by_id("test-456")
            assert result is None


class TestExecutionRepository:
    """Tests for ExecutionRepository class."""

    def test_create_execution(self, db: Database) -> None:
        """Test creating an execution record."""
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-001",
                workflow_name="my-workflow",
                workflow_path="/path/to/workflow.yaml",
                status=ExecutionStatus.RUNNING,
                trigger_type="manual",
                inputs={"key": "value"},
            )
            result = repo.create(execution)

            assert result.id == "exec-001"
            assert result.workflow_name == "my-workflow"
            assert result.status == ExecutionStatus.RUNNING

    def test_update_execution(self, db: Database) -> None:
        """Test updating an execution record."""
        # Create
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-002",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.RUNNING,
            )
            repo.create(execution)

        # Update
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = repo.get_by_id("exec-002")
            assert execution is not None
            execution.status = ExecutionStatus.SUCCESS
            execution.finished_at = datetime.now(UTC)
            execution.duration_ms = 1500
            repo.update(execution)

        # Verify
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            result = repo.get_by_id("exec-002")
            assert result is not None
            assert result.status == ExecutionStatus.SUCCESS
            assert result.duration_ms == 1500

    def test_get_by_id(self, db: Database) -> None:
        """Test getting execution by ID."""
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-003",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.SUCCESS,
            )
            repo.create(execution)

        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            result = repo.get_by_id("exec-003")
            assert result is not None
            assert result.id == "exec-003"

            # Non-existent
            result = repo.get_by_id("non-existent")
            assert result is None

    def test_get_by_workflow(self, db: Database) -> None:
        """Test getting executions by workflow name."""
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            for i in range(5):
                execution = Execution(
                    id=f"exec-wf-{i}",
                    workflow_name="workflow-a",
                    workflow_path="/test",
                    status=ExecutionStatus.SUCCESS if i % 2 == 0 else ExecutionStatus.FAILED,
                )
                repo.create(execution)

            # Different workflow
            execution = Execution(
                id="exec-wf-other",
                workflow_name="workflow-b",
                workflow_path="/test",
                status=ExecutionStatus.SUCCESS,
            )
            repo.create(execution)

        with db.session_scope() as session:
            repo = ExecutionRepository(session)

            # Get all for workflow-a
            results = repo.get_by_workflow("workflow-a")
            assert len(results) == 5

            # With limit
            results = repo.get_by_workflow("workflow-a", limit=2)
            assert len(results) == 2

            # With status filter
            results = repo.get_by_workflow("workflow-a", status=ExecutionStatus.SUCCESS)
            assert len(results) == 3  # 0, 2, 4

    def test_get_recent(self, db: Database) -> None:
        """Test getting recent executions."""
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            for i in range(10):
                execution = Execution(
                    id=f"exec-recent-{i}",
                    workflow_name=f"workflow-{i % 3}",
                    workflow_path="/test",
                    status=ExecutionStatus.SUCCESS,
                )
                repo.create(execution)

        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            results = repo.get_recent(limit=5)
            assert len(results) == 5

    def test_cleanup_old(self, db: Database) -> None:
        """Test cleaning up old executions."""
        now = datetime.now(UTC)
        old_date = now - timedelta(days=40)
        recent_date = now - timedelta(days=10)

        with db.session_scope() as session:
            repo = ExecutionRepository(session)

            # Old execution
            execution_old = Execution(
                id="exec-old",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.SUCCESS,
                started_at=old_date,
            )
            repo.create(execution_old)

            # Recent execution
            execution_recent = Execution(
                id="exec-recent",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.SUCCESS,
                started_at=recent_date,
            )
            repo.create(execution_recent)

        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            deleted = repo.cleanup_old(days=30)
            assert deleted == 1

        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            assert repo.get_by_id("exec-old") is None
            assert repo.get_by_id("exec-recent") is not None

    def test_delete_execution(self, db: Database) -> None:
        """Test deleting an execution."""
        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-delete",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.SUCCESS,
            )
            repo.create(execution)

        with db.session_scope() as session:
            repo = ExecutionRepository(session)
            result = repo.delete("exec-delete")
            assert result is True

            # Delete non-existent
            result = repo.delete("non-existent")
            assert result is False


class TestNodeExecutionRepository:
    """Tests for NodeExecutionRepository class."""

    def test_create_node_execution(self, db: Database) -> None:
        """Test creating a node execution record."""
        # First create parent execution
        with db.session_scope() as session:
            exec_repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-node-001",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.RUNNING,
            )
            exec_repo.create(execution)

        with db.session_scope() as session:
            repo = NodeExecutionRepository(session)
            node_exec = NodeExecution(
                execution_id="exec-node-001",
                node_id="step-1",
                node_type="shell",
                status="success",
                stdout="Hello World",
                duration_ms=100,
            )
            result = repo.create(node_exec)

            assert result.id is not None
            assert result.node_id == "step-1"

    def test_create_batch(self, db: Database) -> None:
        """Test creating multiple node executions at once."""
        # First create parent execution
        with db.session_scope() as session:
            exec_repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-node-batch",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.RUNNING,
            )
            exec_repo.create(execution)

        with db.session_scope() as session:
            repo = NodeExecutionRepository(session)
            nodes = [
                NodeExecution(
                    execution_id="exec-node-batch",
                    node_id=f"step-{i}",
                    node_type="shell",
                    status="success",
                )
                for i in range(3)
            ]
            results = repo.create_batch(nodes)
            assert len(results) == 3

    def test_get_by_execution(self, db: Database) -> None:
        """Test getting node executions for a workflow execution."""
        # First create parent execution
        with db.session_scope() as session:
            exec_repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-node-get",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.RUNNING,
            )
            exec_repo.create(execution)

        now = datetime.now(UTC)
        with db.session_scope() as session:
            repo = NodeExecutionRepository(session)
            nodes = [
                NodeExecution(
                    execution_id="exec-node-get",
                    node_id=f"step-{i}",
                    node_type="shell",
                    status="success",
                    started_at=now + timedelta(seconds=i),
                )
                for i in range(3)
            ]
            repo.create_batch(nodes)

        with db.session_scope() as session:
            repo = NodeExecutionRepository(session)
            results = repo.get_by_execution("exec-node-get")
            assert len(results) == 3
            # Should be ordered by started_at
            assert results[0].node_id == "step-0"
            assert results[2].node_id == "step-2"

    def test_cascade_delete(self, db: Database) -> None:
        """Test that node executions are deleted when parent execution is deleted."""
        # Create execution with nodes
        with db.session_scope() as session:
            exec_repo = ExecutionRepository(session)
            execution = Execution(
                id="exec-cascade",
                workflow_name="test",
                workflow_path="/test",
                status=ExecutionStatus.RUNNING,
            )
            exec_repo.create(execution)

            node_repo = NodeExecutionRepository(session)
            nodes = [
                NodeExecution(
                    execution_id="exec-cascade",
                    node_id=f"step-{i}",
                    node_type="shell",
                    status="success",
                )
                for i in range(3)
            ]
            node_repo.create_batch(nodes)

        # Delete parent
        with db.session_scope() as session:
            exec_repo = ExecutionRepository(session)
            exec_repo.delete("exec-cascade")

        # Verify nodes are also deleted
        with db.session_scope() as session:
            node_repo = NodeExecutionRepository(session)
            results = node_repo.get_by_execution("exec-cascade")
            assert len(results) == 0


class TestScheduleRepository:
    """Tests for ScheduleRepository class."""

    def test_create_schedule(self, db: Database) -> None:
        """Test creating a schedule record."""
        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = Schedule(
                workflow_name="scheduled-workflow",
                workflow_path="/test/workflow.yaml",
                enabled=1,
                trigger_config={"type": "cron", "cron": "0 9 * * *"},
            )
            result = repo.create(schedule)

            assert result.id is not None
            assert result.workflow_name == "scheduled-workflow"
            assert result.enabled == 1

    def test_get_by_workflow(self, db: Database) -> None:
        """Test getting schedule by workflow name."""
        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = Schedule(
                workflow_name="my-scheduled",
                workflow_path="/test/workflow.yaml",
                enabled=1,
            )
            repo.create(schedule)

        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            result = repo.get_by_workflow("my-scheduled")
            assert result is not None
            assert result.workflow_name == "my-scheduled"

            # Non-existent
            result = repo.get_by_workflow("non-existent")
            assert result is None

    def test_get_enabled(self, db: Database) -> None:
        """Test getting all enabled schedules."""
        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            for i in range(5):
                schedule = Schedule(
                    workflow_name=f"schedule-{i}",
                    workflow_path=f"/test/{i}.yaml",
                    enabled=1 if i % 2 == 0 else 0,  # 0, 2, 4 enabled
                )
                repo.create(schedule)

        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            results = repo.get_enabled()
            assert len(results) == 3

    def test_get_all(self, db: Database) -> None:
        """Test getting all schedules."""
        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            for i in range(3):
                schedule = Schedule(
                    workflow_name=f"all-{i}",
                    workflow_path=f"/test/{i}.yaml",
                    enabled=1,
                )
                repo.create(schedule)

        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            results = repo.get_all()
            assert len(results) == 3

    def test_delete_schedule(self, db: Database) -> None:
        """Test deleting a schedule."""
        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule = Schedule(
                workflow_name="delete-me",
                workflow_path="/test/workflow.yaml",
                enabled=1,
            )
            repo.create(schedule)

        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            result = repo.delete("delete-me")
            assert result is True

            result = repo.delete("non-existent")
            assert result is False

    def test_unique_workflow_name(self, db: Database) -> None:
        """Test that workflow_name must be unique."""
        from sqlalchemy.exc import IntegrityError

        with db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule1 = Schedule(
                workflow_name="unique-test",
                workflow_path="/test/1.yaml",
                enabled=1,
            )
            repo.create(schedule1)

        # Trying to create another with same name should fail
        with pytest.raises(IntegrityError), db.session_scope() as session:
            repo = ScheduleRepository(session)
            schedule2 = Schedule(
                workflow_name="unique-test",
                workflow_path="/test/2.yaml",
                enabled=1,
            )
            repo.create(schedule2)

"""Tests for execution API routes."""

from __future__ import annotations

import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from flowpilot.api.routes.executions import (
    ConnectionManager,
    router,
    set_database,
)
from flowpilot.storage.database import Database
from flowpilot.storage.models import Execution, ExecutionStatus, NodeExecution
from flowpilot.storage.repositories import ExecutionRepository, NodeExecutionRepository

if TYPE_CHECKING:
    from collections.abc import Generator


class ExecutionData(NamedTuple):
    """Test data for an execution."""

    id: str
    workflow_name: str
    workflow_path: str
    status: str
    trigger_type: str | None
    inputs: dict[str, Any]


class NodeData(NamedTuple):
    """Test data for a node execution."""

    id: int
    execution_id: str
    node_id: str


@pytest.fixture
def test_db() -> Generator[Database, None, None]:
    """Create a temporary file-based database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.create_tables()
        set_database(db)
        yield db
        set_database(None)


@pytest.fixture
def client(test_db: Database) -> TestClient:
    """Create a test client with the execution routes."""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def create_sample_execution(db: Database) -> ExecutionData:
    """Create a sample execution in the database."""
    exec_id = str(uuid.uuid4())
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        execution = Execution(
            id=exec_id,
            workflow_name="test-workflow",
            workflow_path="/path/to/workflow.yaml",
            status=ExecutionStatus.SUCCESS,
            trigger_type="manual",
            inputs={"key": "value"},
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=1000,
        )
        repo.create(execution)

    return ExecutionData(
        id=exec_id,
        workflow_name="test-workflow",
        workflow_path="/path/to/workflow.yaml",
        status="success",
        trigger_type="manual",
        inputs={"key": "value"},
    )


def create_sample_node_execution(db: Database, execution_id: str) -> NodeData:
    """Create a sample node execution in the database."""
    with db.session_scope() as session:
        repo = NodeExecutionRepository(session)
        node = NodeExecution(
            execution_id=execution_id,
            node_id="node-1",
            node_type="shell",
            status="success",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            duration_ms=500,
            stdout="Hello, World!",
            stderr="",
            output="{}",
        )
        repo.create(node)
        node_id = node.id

    return NodeData(
        id=node_id,
        execution_id=execution_id,
        node_id="node-1",
    )


class TestListExecutions:
    """Tests for GET /api/executions endpoint."""

    def test_list_empty(self, client: TestClient, test_db: Database) -> None:
        """Test listing when no executions exist."""
        response = client.get("/api/executions")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_executions(self, client: TestClient, test_db: Database) -> None:
        """Test listing with existing executions."""
        sample = create_sample_execution(test_db)

        response = client.get("/api/executions")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample.id
        assert data[0]["workflow_name"] == "test-workflow"
        assert data[0]["status"] == "success"

    def test_filter_by_workflow(self, client: TestClient, test_db: Database) -> None:
        """Test filtering by workflow name."""
        create_sample_execution(test_db)

        # Create another execution with different workflow
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)
            other_execution = Execution(
                id=str(uuid.uuid4()),
                workflow_name="other-workflow",
                workflow_path="/path/to/other.yaml",
                status=ExecutionStatus.RUNNING,
            )
            repo.create(other_execution)

        response = client.get("/api/executions?workflow=test-workflow")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["workflow_name"] == "test-workflow"

    def test_filter_by_status(self, client: TestClient, test_db: Database) -> None:
        """Test filtering by status."""
        create_sample_execution(test_db)

        # Create a running execution
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)
            running = Execution(
                id=str(uuid.uuid4()),
                workflow_name="running-workflow",
                workflow_path="/path/to/workflow.yaml",
                status=ExecutionStatus.RUNNING,
            )
            repo.create(running)

        response = client.get("/api/executions?status=running")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "running"

    def test_invalid_status_filter(self, client: TestClient, test_db: Database) -> None:
        """Test filtering with invalid status returns error."""
        response = client.get("/api/executions?status=invalid")
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_pagination(self, client: TestClient, test_db: Database) -> None:
        """Test pagination with limit and offset."""
        create_sample_execution(test_db)

        # Create more executions
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)
            for i in range(5):
                execution = Execution(
                    id=str(uuid.uuid4()),
                    workflow_name=f"workflow-{i}",
                    workflow_path="/path/to/workflow.yaml",
                    status=ExecutionStatus.SUCCESS,
                )
                repo.create(execution)

        response = client.get("/api/executions?limit=2&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        response = client.get("/api/executions?limit=2&offset=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2


class TestGetExecutionStats:
    """Tests for GET /api/executions/stats endpoint."""

    def test_stats_empty(self, client: TestClient, test_db: Database) -> None:
        """Test stats when no executions exist."""
        response = client.get("/api/executions/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_executions"] == 0
        assert data["success_count"] == 0
        assert data["success_rate"] == 0.0
        assert data["executions_by_workflow"] == {}

    def test_stats_with_executions(self, client: TestClient, test_db: Database) -> None:
        """Test stats with various executions."""
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)

            # Create executions with different statuses
            for status in [
                ExecutionStatus.SUCCESS,
                ExecutionStatus.SUCCESS,
                ExecutionStatus.FAILED,
                ExecutionStatus.RUNNING,
            ]:
                execution = Execution(
                    id=str(uuid.uuid4()),
                    workflow_name="test-workflow",
                    workflow_path="/path/to/workflow.yaml",
                    status=status,
                    duration_ms=1000 if status == ExecutionStatus.SUCCESS else None,
                )
                repo.create(execution)

        response = client.get("/api/executions/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_executions"] == 4
        assert data["success_count"] == 2
        assert data["failed_count"] == 1
        assert data["running_count"] == 1
        # Success rate = 2 / (2 + 1) = 0.666...
        assert abs(data["success_rate"] - 2 / 3) < 0.01
        assert data["avg_duration_ms"] == 1000.0
        assert data["executions_by_workflow"]["test-workflow"] == 4

    def test_stats_filter_by_workflow(self, client: TestClient, test_db: Database) -> None:
        """Test stats filtered by workflow."""
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)

            # Create executions for different workflows
            for workflow in ["workflow-a", "workflow-b"]:
                execution = Execution(
                    id=str(uuid.uuid4()),
                    workflow_name=workflow,
                    workflow_path=f"/path/to/{workflow}.yaml",
                    status=ExecutionStatus.SUCCESS,
                )
                repo.create(execution)

        response = client.get("/api/executions/stats?workflow=workflow-a")
        assert response.status_code == 200
        data = response.json()
        assert data["total_executions"] == 1
        assert "workflow-a" in data["executions_by_workflow"]
        assert "workflow-b" not in data["executions_by_workflow"]


class TestGetExecution:
    """Tests for GET /api/executions/{id} endpoint."""

    def test_get_execution(self, client: TestClient, test_db: Database) -> None:
        """Test getting execution details."""
        sample = create_sample_execution(test_db)
        create_sample_node_execution(test_db, sample.id)

        response = client.get(f"/api/executions/{sample.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample.id
        assert data["workflow_name"] == "test-workflow"
        assert data["status"] == "success"
        assert data["inputs"] == {"key": "value"}
        assert len(data["node_executions"]) == 1
        assert data["node_executions"][0]["node_id"] == "node-1"

    def test_get_execution_not_found(self, client: TestClient, test_db: Database) -> None:
        """Test getting non-existent execution."""
        response = client.get(f"/api/executions/{uuid.uuid4()}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCancelExecution:
    """Tests for DELETE /api/executions/{id} endpoint."""

    def test_cancel_running_execution(self, client: TestClient, test_db: Database) -> None:
        """Test cancelling a running execution."""
        exec_id = str(uuid.uuid4())
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id=exec_id,
                workflow_name="test-workflow",
                workflow_path="/path/to/workflow.yaml",
                status=ExecutionStatus.RUNNING,
            )
            repo.create(execution)

        response = client.delete(f"/api/executions/{exec_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == exec_id
        assert data["status"] == "cancelled"

    def test_cancel_pending_execution(self, client: TestClient, test_db: Database) -> None:
        """Test cancelling a pending execution."""
        exec_id = str(uuid.uuid4())
        with test_db.session_scope() as session:
            repo = ExecutionRepository(session)
            execution = Execution(
                id=exec_id,
                workflow_name="test-workflow",
                workflow_path="/path/to/workflow.yaml",
                status=ExecutionStatus.PENDING,
            )
            repo.create(execution)

        response = client.delete(f"/api/executions/{exec_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_cancel_completed_execution_fails(self, client: TestClient, test_db: Database) -> None:
        """Test that cancelling a completed execution fails."""
        sample = create_sample_execution(test_db)
        response = client.delete(f"/api/executions/{sample.id}")
        assert response.status_code == 400
        assert "Cannot cancel" in response.json()["detail"]

    def test_cancel_not_found(self, client: TestClient, test_db: Database) -> None:
        """Test cancelling non-existent execution."""
        response = client.delete(f"/api/executions/{uuid.uuid4()}")
        assert response.status_code == 404


class TestGetExecutionLogs:
    """Tests for GET /api/executions/{id}/logs endpoint."""

    def test_get_logs(self, client: TestClient, test_db: Database) -> None:
        """Test getting execution logs."""
        sample = create_sample_execution(test_db)
        create_sample_node_execution(test_db, sample.id)

        response = client.get(f"/api/executions/{sample.id}/logs")
        assert response.status_code == 200
        data = response.json()
        assert data["execution_id"] == sample.id
        assert data["total"] == 1
        assert data["page"] == 1
        assert data["page_size"] == 50
        assert len(data["logs"]) == 1
        assert data["logs"][0]["node_id"] == "node-1"
        assert data["logs"][0]["stdout"] == "Hello, World!"

    def test_get_logs_pagination(self, client: TestClient, test_db: Database) -> None:
        """Test paginated log retrieval."""
        sample = create_sample_execution(test_db)

        # Create more node executions
        with test_db.session_scope() as session:
            repo = NodeExecutionRepository(session)
            for i in range(10):
                node = NodeExecution(
                    execution_id=sample.id,
                    node_id=f"node-{i}",
                    node_type="shell",
                    status="success",
                )
                repo.create(node)

        response = client.get(f"/api/executions/{sample.id}/logs?page=1&page_size=5")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 10
        assert len(data["logs"]) == 5
        assert data["page"] == 1
        assert data["page_size"] == 5

        # Get second page
        response = client.get(f"/api/executions/{sample.id}/logs?page=2&page_size=5")
        data = response.json()
        assert len(data["logs"]) == 5
        assert data["page"] == 2

    def test_get_logs_not_found(self, client: TestClient, test_db: Database) -> None:
        """Test getting logs for non-existent execution."""
        response = client.get(f"/api/executions/{uuid.uuid4()}/logs")
        assert response.status_code == 404


class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager."""

    @pytest.fixture
    def manager(self) -> ConnectionManager:
        """Create a connection manager instance."""
        return ConnectionManager()

    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, manager: ConnectionManager) -> None:
        """Test connecting and disconnecting a WebSocket."""
        mock_ws = AsyncMock()
        execution_id = "test-exec"

        await manager.connect(mock_ws, execution_id)
        mock_ws.accept.assert_called_once()
        assert execution_id in manager._connections
        assert mock_ws in manager._connections[execution_id]

        await manager.disconnect(mock_ws, execution_id)
        assert execution_id not in manager._connections

    @pytest.mark.asyncio
    async def test_broadcast(self, manager: ConnectionManager) -> None:
        """Test broadcasting a message to all connections."""
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        execution_id = "test-exec"

        await manager.connect(mock_ws1, execution_id)
        await manager.connect(mock_ws2, execution_id)

        from flowpilot.api.schemas.executions import WebSocketMessage

        message = WebSocketMessage(
            type="log",
            execution_id=execution_id,
            timestamp=datetime.now(),
            data={"test": "data"},
        )

        await manager.broadcast(execution_id, message)

        assert mock_ws1.send_json.call_count == 1
        assert mock_ws2.send_json.call_count == 1

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self, manager: ConnectionManager) -> None:
        """Test that failed connections are removed during broadcast."""
        mock_ws_ok = AsyncMock()
        mock_ws_fail = AsyncMock()
        mock_ws_fail.send_json.side_effect = Exception("Connection lost")
        execution_id = "test-exec"

        await manager.connect(mock_ws_ok, execution_id)
        await manager.connect(mock_ws_fail, execution_id)

        from flowpilot.api.schemas.executions import WebSocketMessage

        message = WebSocketMessage(
            type="log",
            execution_id=execution_id,
            timestamp=datetime.now(),
            data={},
        )

        await manager.broadcast(execution_id, message)

        # OK connection should still be there
        assert mock_ws_ok in manager._connections.get(execution_id, [])


class TestDatabaseNotConfigured:
    """Test behavior when database is not configured."""

    def test_list_without_db(self) -> None:
        """Test listing executions without database configured."""
        app = FastAPI()
        app.include_router(router)
        set_database(None)
        test_client = TestClient(app)

        response = test_client.get("/api/executions")
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"].lower()

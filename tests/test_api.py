"""Tests for FlowPilot FastAPI server."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from flowpilot.api import create_app


@pytest.fixture
def temp_workflows_dir() -> Generator[Path, None, None]:
    """Create a temporary workflows directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_workflow_content() -> str:
    """Sample valid workflow YAML content."""
    return """name: test-workflow
description: A test workflow
version: 1
triggers:
  - type: manual
nodes:
  - id: step-1
    type: shell
    command: echo "Hello"
"""


@pytest.fixture
def mock_runner() -> MagicMock:
    """Create a mock workflow runner."""
    runner = MagicMock()
    runner.run = AsyncMock()
    return runner


@pytest.fixture
def client(temp_workflows_dir: Path) -> TestClient:
    """Create a test client without runner."""
    app = create_app(workflows_dir=temp_workflows_dir, enable_cors=True)
    return TestClient(app)


@pytest.fixture
def client_with_runner(temp_workflows_dir: Path, mock_runner: MagicMock) -> TestClient:
    """Create a test client with mock runner."""
    app = create_app(workflows_dir=temp_workflows_dir, runner=mock_runner, enable_cors=True)
    return TestClient(app)


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    def test_health_check(self, client: TestClient) -> None:
        """Test main health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "flowpilot"
        assert "timestamp" in data
        assert "version" in data

    def test_readiness_check(self, client: TestClient) -> None:
        """Test readiness check endpoint."""
        response = client.get("/api/health/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data

    def test_liveness_check(self, client: TestClient) -> None:
        """Test liveness check endpoint."""
        response = client.get("/api/health/live")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data


class TestWorkflowListEndpoint:
    """Tests for workflow list endpoint."""

    def test_list_empty_workflows(self, client: TestClient) -> None:
        """Test listing workflows when directory is empty."""
        response = client.get("/api/workflows")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_workflows(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test listing workflows."""
        # Create a workflow file
        workflow_path = temp_workflows_dir / "test-workflow.yaml"
        workflow_path.write_text(sample_workflow_content)

        response = client.get("/api/workflows")
        assert response.status_code == 200
        workflows = response.json()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "test-workflow"
        assert workflows[0]["description"] == "A test workflow"
        assert workflows[0]["version"] == 1

    def test_list_workflows_with_search(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test searching workflows."""
        # Create workflow files
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        other_workflow = sample_workflow_content.replace("test-workflow", "other-workflow")
        (temp_workflows_dir / "other-workflow.yaml").write_text(other_workflow)

        # Search for "test"
        response = client.get("/api/workflows?search=test")
        assert response.status_code == 200
        workflows = response.json()
        assert len(workflows) == 1
        assert workflows[0]["name"] == "test-workflow"

    def test_list_workflows_pagination(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test workflow pagination."""
        # Create multiple workflows
        for i in range(5):
            workflow = sample_workflow_content.replace("test-workflow", f"workflow-{i:02d}")
            (temp_workflows_dir / f"workflow-{i:02d}.yaml").write_text(workflow)

        # First page
        response = client.get("/api/workflows?page=1&page_size=2")
        assert response.status_code == 200
        workflows = response.json()
        assert len(workflows) == 2

        # Second page
        response = client.get("/api/workflows?page=2&page_size=2")
        assert response.status_code == 200
        workflows = response.json()
        assert len(workflows) == 2


class TestWorkflowCreateEndpoint:
    """Tests for workflow create endpoint."""

    def test_create_workflow(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test creating a workflow."""
        response = client.post(
            "/api/workflows",
            json={"name": "test-workflow", "content": sample_workflow_content},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "test-workflow"
        assert data["description"] == "A test workflow"
        assert data["node_count"] == 1

        # Verify file was created
        assert (temp_workflows_dir / "test-workflow.yaml").exists()

    def test_create_workflow_conflict(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test creating a workflow that already exists."""
        # Create workflow first
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client.post(
            "/api/workflows",
            json={"name": "test-workflow", "content": sample_workflow_content},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_workflow_invalid_yaml(self, client: TestClient) -> None:
        """Test creating a workflow with invalid YAML."""
        response = client.post(
            "/api/workflows",
            json={"name": "bad-workflow", "content": "invalid: [yaml: content"},
        )
        assert response.status_code == 400
        assert "Invalid workflow YAML" in response.json()["detail"]

    def test_create_workflow_name_mismatch(
        self, client: TestClient, sample_workflow_content: str
    ) -> None:
        """Test creating a workflow with mismatched name."""
        response = client.post(
            "/api/workflows",
            json={"name": "wrong-name", "content": sample_workflow_content},
        )
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]


class TestWorkflowGetEndpoint:
    """Tests for workflow get endpoint."""

    def test_get_workflow(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test getting a workflow."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client.get("/api/workflows/test-workflow")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-workflow"
        assert data["content"] == sample_workflow_content
        assert data["node_count"] == 1

    def test_get_workflow_not_found(self, client: TestClient) -> None:
        """Test getting a workflow that doesn't exist."""
        response = client.get("/api/workflows/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestWorkflowUpdateEndpoint:
    """Tests for workflow update endpoint."""

    def test_update_workflow(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test updating a workflow."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        updated_content = sample_workflow_content.replace("A test workflow", "Updated description")

        response = client.put(
            "/api/workflows/test-workflow",
            json={"content": updated_content},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == "Updated description"

    def test_update_workflow_not_found(
        self, client: TestClient, sample_workflow_content: str
    ) -> None:
        """Test updating a workflow that doesn't exist."""
        response = client.put(
            "/api/workflows/nonexistent",
            json={"content": sample_workflow_content},
        )
        assert response.status_code == 404

    def test_update_workflow_invalid_yaml(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test updating a workflow with invalid YAML."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client.put(
            "/api/workflows/test-workflow",
            json={"content": "invalid: [yaml"},
        )
        assert response.status_code == 400

    def test_update_workflow_name_mismatch(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test updating with mismatched workflow name."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        wrong_name_content = sample_workflow_content.replace("test-workflow", "different-name")

        response = client.put(
            "/api/workflows/test-workflow",
            json={"content": wrong_name_content},
        )
        assert response.status_code == 400
        assert "does not match" in response.json()["detail"]


class TestWorkflowDeleteEndpoint:
    """Tests for workflow delete endpoint."""

    def test_delete_workflow(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test deleting a workflow."""
        workflow_path = temp_workflows_dir / "test-workflow.yaml"
        workflow_path.write_text(sample_workflow_content)
        assert workflow_path.exists()

        response = client.delete("/api/workflows/test-workflow")
        assert response.status_code == 204
        assert not workflow_path.exists()

    def test_delete_workflow_not_found(self, client: TestClient) -> None:
        """Test deleting a workflow that doesn't exist."""
        response = client.delete("/api/workflows/nonexistent")
        assert response.status_code == 404


class TestWorkflowValidateEndpoint:
    """Tests for workflow validate endpoint."""

    def test_validate_valid_workflow(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test validating a valid workflow."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client.get("/api/workflows/test-workflow/validate")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_validate_invalid_workflow(self, client: TestClient, temp_workflows_dir: Path) -> None:
        """Test validating an invalid workflow."""
        # Write invalid workflow content
        invalid_content = "name: invalid\nnodes: []"  # nodes must have at least one
        (temp_workflows_dir / "invalid.yaml").write_text(invalid_content)

        response = client.get("/api/workflows/invalid/validate")
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_validate_workflow_not_found(self, client: TestClient) -> None:
        """Test validating a workflow that doesn't exist."""
        response = client.get("/api/workflows/nonexistent/validate")
        assert response.status_code == 404


class TestWorkflowRunEndpoint:
    """Tests for workflow run endpoint."""

    def test_run_workflow_no_runner(
        self, client: TestClient, temp_workflows_dir: Path, sample_workflow_content: str
    ) -> None:
        """Test running workflow when runner is not configured."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client.post("/api/workflows/test-workflow/run")
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    def test_run_workflow(
        self,
        client_with_runner: TestClient,
        temp_workflows_dir: Path,
        sample_workflow_content: str,
    ) -> None:
        """Test running a workflow."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client_with_runner.post("/api/workflows/test-workflow/run")
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data
        assert data["workflow"] == "test-workflow"
        assert data["status"] == "accepted"

    def test_run_workflow_with_inputs(
        self,
        client_with_runner: TestClient,
        temp_workflows_dir: Path,
        sample_workflow_content: str,
    ) -> None:
        """Test running a workflow with inputs."""
        (temp_workflows_dir / "test-workflow.yaml").write_text(sample_workflow_content)

        response = client_with_runner.post(
            "/api/workflows/test-workflow/run",
            json={"inputs": {"key": "value"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert "execution_id" in data

    def test_run_workflow_not_found(self, client_with_runner: TestClient) -> None:
        """Test running a workflow that doesn't exist."""
        response = client_with_runner.post("/api/workflows/nonexistent/run")
        assert response.status_code == 404


class TestCORSMiddleware:
    """Tests for CORS middleware configuration."""

    def test_cors_headers_present(self, client: TestClient) -> None:
        """Test that CORS headers are present in response."""
        response = client.options(
            "/api/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # CORS preflight should succeed
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


class TestOpenAPIDocumentation:
    """Tests for OpenAPI documentation endpoints."""

    def test_openapi_schema(self, client: TestClient) -> None:
        """Test OpenAPI schema endpoint."""
        response = client.get("/api/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert schema["info"]["title"] == "FlowPilot API"
        assert "paths" in schema

    def test_docs_endpoint(self, client: TestClient) -> None:
        """Test Swagger UI documentation endpoint."""
        response = client.get("/api/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_redoc_endpoint(self, client: TestClient) -> None:
        """Test ReDoc documentation endpoint."""
        response = client.get("/api/redoc")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

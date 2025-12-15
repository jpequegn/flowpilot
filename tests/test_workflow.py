"""Tests for FlowPilot Workflow model."""

import pytest
from pydantic import ValidationError

from flowpilot.models import InputDefinition, Workflow, WorkflowSettings


class TestInputDefinition:
    """Tests for InputDefinition model."""

    def test_default_input(self) -> None:
        """Test input with defaults."""
        input_def = InputDefinition()
        assert input_def.type == "string"
        assert input_def.default is None
        assert input_def.required is False
        assert input_def.description is None

    def test_full_input(self) -> None:
        """Test input with all fields."""
        input_def = InputDefinition(
            type="number",
            default=10,
            required=True,
            description="Max items to process",
        )
        assert input_def.type == "number"
        assert input_def.default == 10
        assert input_def.required is True


class TestWorkflowSettings:
    """Tests for WorkflowSettings model."""

    def test_default_settings(self) -> None:
        """Test default workflow settings."""
        settings = WorkflowSettings()
        assert settings.timeout == 300
        assert settings.retry == 0
        assert settings.retry_delay == 5
        assert settings.on_error == "stop"

    def test_custom_settings(self) -> None:
        """Test custom workflow settings."""
        settings = WorkflowSettings(timeout=600, retry=3, retry_delay=10, on_error="continue")
        assert settings.timeout == 600
        assert settings.retry == 3
        assert settings.on_error == "continue"

    def test_invalid_on_error(self) -> None:
        """Test invalid on_error value."""
        with pytest.raises(ValidationError):
            WorkflowSettings(on_error="invalid")


class TestWorkflow:
    """Tests for Workflow model."""

    def test_minimal_workflow(self) -> None:
        """Test workflow with minimal config."""
        workflow = Workflow(
            name="test-workflow",
            nodes=[{"type": "shell", "id": "step-1", "command": "echo hello"}],
        )
        assert workflow.name == "test-workflow"
        assert workflow.description == ""
        assert workflow.version == 1
        assert len(workflow.triggers) == 1
        assert workflow.triggers[0].type == "manual"
        assert len(workflow.nodes) == 1

    def test_full_workflow(self) -> None:
        """Test workflow with all options."""
        workflow = Workflow(
            name="full-workflow",
            description="A complete workflow",
            version=2,
            triggers=[
                {"type": "cron", "schedule": "0 9 * * *"},
                {"type": "manual"},
            ],
            inputs={
                "name": {"type": "string", "default": "World"},
            },
            nodes=[
                {"type": "shell", "id": "greet", "command": "echo hello"},
                {"type": "shell", "id": "done", "command": "echo done", "depends_on": ["greet"]},
            ],
            settings={"timeout": 600, "retry": 2},
        )
        assert workflow.version == 2
        assert len(workflow.triggers) == 2
        assert "name" in workflow.inputs
        assert len(workflow.nodes) == 2

    def test_invalid_workflow_name(self) -> None:
        """Test invalid workflow name."""
        with pytest.raises(ValidationError):
            Workflow(
                name="Invalid Name",
                nodes=[{"type": "shell", "id": "node", "command": "echo"}],
            )

    def test_invalid_workflow_name_starts_with_number(self) -> None:
        """Test workflow name cannot start with number."""
        with pytest.raises(ValidationError):
            Workflow(
                name="1-workflow",
                nodes=[{"type": "shell", "id": "node", "command": "echo"}],
            )

    def test_workflow_requires_nodes(self) -> None:
        """Test workflow requires at least one node."""
        with pytest.raises(ValidationError):
            Workflow(name="empty-workflow", nodes=[])

    def test_duplicate_node_ids(self) -> None:
        """Test duplicate node IDs are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="dup-nodes",
                nodes=[
                    {"type": "shell", "id": "same-id", "command": "echo 1"},
                    {"type": "shell", "id": "same-id", "command": "echo 2"},
                ],
            )
        assert "Duplicate node IDs" in str(exc_info.value)

    def test_invalid_depends_on_reference(self) -> None:
        """Test depends_on must reference existing node."""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="bad-ref",
                nodes=[
                    {
                        "type": "shell",
                        "id": "node",
                        "command": "echo",
                        "depends_on": ["nonexistent"],
                    }
                ],
            )
        assert "depends on unknown node" in str(exc_info.value)

    def test_invalid_condition_then_reference(self) -> None:
        """Test condition 'then' must reference existing node."""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="bad-then",
                nodes=[
                    {
                        "type": "condition",
                        "id": "check",
                        "if": "true",
                        "then": "nonexistent",
                    }
                ],
            )
        assert "references unknown 'then' node" in str(exc_info.value)

    def test_invalid_condition_else_reference(self) -> None:
        """Test condition 'else' must reference existing node."""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="bad-else",
                nodes=[
                    {"type": "shell", "id": "success", "command": "echo ok"},
                    {
                        "type": "condition",
                        "id": "check",
                        "if": "true",
                        "then": "success",
                        "else": "nonexistent",
                    },
                ],
            )
        assert "references unknown 'else' node" in str(exc_info.value)

    def test_invalid_loop_do_reference(self) -> None:
        """Test loop 'do' must reference existing node."""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="bad-loop",
                nodes=[
                    {
                        "type": "loop",
                        "id": "iterate",
                        "for": "items",
                        "do": ["nonexistent"],
                    }
                ],
            )
        assert "references unknown 'do' node" in str(exc_info.value)

    def test_invalid_parallel_nodes_reference(self) -> None:
        """Test parallel nodes must reference existing nodes."""
        with pytest.raises(ValidationError) as exc_info:
            Workflow(
                name="bad-parallel",
                nodes=[
                    {"type": "shell", "id": "task-a", "command": "echo a"},
                    {
                        "type": "parallel",
                        "id": "run-parallel",
                        "nodes": ["task-a", "nonexistent"],
                    },
                ],
            )
        assert "references unknown node" in str(exc_info.value)

    def test_get_node(self) -> None:
        """Test get_node method."""
        workflow = Workflow(
            name="test",
            nodes=[
                {"type": "shell", "id": "first", "command": "echo 1"},
                {"type": "shell", "id": "second", "command": "echo 2"},
            ],
        )
        node = workflow.get_node("first")
        assert node is not None
        assert node.id == "first"

        missing = workflow.get_node("nonexistent")
        assert missing is None

    def test_get_node_ids(self) -> None:
        """Test get_node_ids method."""
        workflow = Workflow(
            name="test",
            nodes=[
                {"type": "shell", "id": "alpha", "command": "echo a"},
                {"type": "shell", "id": "beta", "command": "echo b"},
            ],
        )
        ids = workflow.get_node_ids()
        assert ids == {"alpha", "beta"}

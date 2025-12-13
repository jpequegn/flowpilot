"""Tests for FlowPilot workflow runner."""

import pytest

from flowpilot.engine import (
    CircularDependencyError,
    ExecutionContext,
    ExecutorRegistry,
    NodeExecutor,
    NodeResult,
    WorkflowRunner,
)
from flowpilot.models import BaseNode, ShellNode, Workflow


class TestWorkflowRunner:
    """Tests for WorkflowRunner class."""

    def setup_method(self) -> None:
        """Clear registry and register test executor."""
        ExecutorRegistry.clear()

        @ExecutorRegistry.register("shell")
        class ShellExecutor(NodeExecutor):
            async def execute(self, node: BaseNode, context: ExecutionContext) -> NodeResult:
                if isinstance(node, ShellNode):
                    # Simulate command execution
                    return NodeResult.success(
                        stdout=f"Executed: {node.command}",
                        output=node.command,
                    )
                return NodeResult.error("Not a shell node")

    @pytest.fixture
    def runner(self) -> WorkflowRunner:
        """Create a workflow runner."""
        return WorkflowRunner()

    @pytest.mark.asyncio
    async def test_run_simple_workflow(self, runner: WorkflowRunner) -> None:
        """Test running simple single-node workflow."""
        workflow = Workflow(
            name="simple",
            nodes=[
                {"type": "shell", "id": "step-1", "command": "echo hello"},
            ],
        )

        context = await runner.run(workflow)

        assert context.status == "success"
        assert "step-1" in context.nodes
        assert context.nodes["step-1"].status == "success"
        assert "Executed: echo hello" in context.nodes["step-1"].stdout

    @pytest.mark.asyncio
    async def test_run_workflow_with_dependencies(self, runner: WorkflowRunner) -> None:
        """Test running workflow with node dependencies."""
        workflow = Workflow(
            name="deps",
            nodes=[
                {"type": "shell", "id": "first", "command": "echo first"},
                {
                    "type": "shell",
                    "id": "second",
                    "command": "echo second",
                    "depends_on": ["first"],
                },
            ],
        )

        context = await runner.run(workflow)

        assert context.status == "success"
        assert context.nodes["first"].status == "success"
        assert context.nodes["second"].status == "success"

    @pytest.mark.asyncio
    async def test_run_workflow_with_inputs(self, runner: WorkflowRunner) -> None:
        """Test running workflow with inputs."""
        workflow = Workflow(
            name="inputs",
            inputs={
                "greeting": {"type": "string", "default": "Hello"},
            },
            nodes=[
                {"type": "shell", "id": "greet", "command": "echo {{ inputs.greeting }}"},
            ],
        )

        context = await runner.run(workflow, inputs={"greeting": "Hi"})

        assert context.inputs["greeting"] == "Hi"
        assert context.status == "success"

    @pytest.mark.asyncio
    async def test_run_workflow_with_default_inputs(self, runner: WorkflowRunner) -> None:
        """Test workflow uses default inputs when not provided."""
        workflow = Workflow(
            name="defaults",
            inputs={
                "count": {"type": "number", "default": 5},
            },
            nodes=[
                {"type": "shell", "id": "run", "command": "echo"},
            ],
        )

        context = await runner.run(workflow)

        assert context.inputs["count"] == 5

    @pytest.mark.asyncio
    async def test_run_workflow_missing_required_input(self, runner: WorkflowRunner) -> None:
        """Test workflow fails with missing required input."""
        workflow = Workflow(
            name="required",
            inputs={
                "name": {"type": "string", "required": True},
            },
            nodes=[
                {"type": "shell", "id": "run", "command": "echo"},
            ],
        )

        with pytest.raises(ValueError, match="Required input"):
            await runner.run(workflow)

    @pytest.mark.asyncio
    async def test_run_workflow_with_custom_execution_id(self, runner: WorkflowRunner) -> None:
        """Test workflow with custom execution ID."""
        workflow = Workflow(
            name="custom-id",
            nodes=[
                {"type": "shell", "id": "run", "command": "echo"},
            ],
        )

        context = await runner.run(workflow, execution_id="my-custom-id")

        assert context.execution_id == "my-custom-id"

    @pytest.mark.asyncio
    async def test_run_workflow_error_stops_execution(self, runner: WorkflowRunner) -> None:
        """Test workflow stops on error when on_error is 'stop'."""
        ExecutorRegistry.clear()

        @ExecutorRegistry.register("shell")
        class FailingExecutor(NodeExecutor):
            async def execute(self, node: BaseNode, context: ExecutionContext) -> NodeResult:
                if node.id == "fail":
                    return NodeResult.error("Intentional failure")
                return NodeResult.success()

        workflow = Workflow(
            name="error-stop",
            settings={"on_error": "stop"},
            nodes=[
                {"type": "shell", "id": "first", "command": "echo"},
                {"type": "shell", "id": "fail", "command": "fail", "depends_on": ["first"]},
                {"type": "shell", "id": "third", "command": "echo", "depends_on": ["fail"]},
            ],
        )

        context = await runner.run(workflow)

        assert context.status == "error"
        assert context.nodes["first"].status == "success"
        assert context.nodes["fail"].status == "error"
        # Third node should not be in results (execution stopped)
        assert "third" not in context.nodes or context.nodes["third"].status == "skipped"


class TestWorkflowRunnerDependencyGraph:
    """Tests for dependency graph building."""

    def setup_method(self) -> None:
        """Clear registry and register test executor."""
        ExecutorRegistry.clear()

        @ExecutorRegistry.register("shell")
        class ShellExecutor(NodeExecutor):
            async def execute(self, node: BaseNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

    @pytest.fixture
    def runner(self) -> WorkflowRunner:
        """Create a workflow runner."""
        return WorkflowRunner()

    @pytest.mark.asyncio
    async def test_circular_dependency_detection(self, runner: WorkflowRunner) -> None:
        """Test circular dependency is detected."""
        workflow = Workflow(
            name="circular",
            nodes=[
                {
                    "type": "shell",
                    "id": "a",
                    "command": "echo",
                    "depends_on": ["b"],
                },
                {
                    "type": "shell",
                    "id": "b",
                    "command": "echo",
                    "depends_on": ["a"],
                },
            ],
        )

        with pytest.raises(CircularDependencyError):
            await runner.run(workflow)

    @pytest.mark.asyncio
    async def test_complex_dependency_graph(self, runner: WorkflowRunner) -> None:
        """Test complex dependency graph is handled correctly."""
        #     a
        #    / \
        #   b   c
        #    \ /
        #     d
        workflow = Workflow(
            name="complex",
            nodes=[
                {"type": "shell", "id": "a", "command": "echo"},
                {"type": "shell", "id": "b", "command": "echo", "depends_on": ["a"]},
                {"type": "shell", "id": "c", "command": "echo", "depends_on": ["a"]},
                {"type": "shell", "id": "d", "command": "echo", "depends_on": ["b", "c"]},
            ],
        )

        context = await runner.run(workflow)

        assert context.status == "success"
        assert all(r.status == "success" for r in context.nodes.values())


class TestWorkflowRunnerValidation:
    """Tests for workflow validation."""

    def setup_method(self) -> None:
        """Clear registry."""
        ExecutorRegistry.clear()

    @pytest.fixture
    def runner(self) -> WorkflowRunner:
        """Create a workflow runner."""
        return WorkflowRunner()

    def test_validate_missing_executor(self, runner: WorkflowRunner) -> None:
        """Test validation catches missing executor."""
        workflow = Workflow(
            name="missing-executor",
            nodes=[
                {"type": "shell", "id": "run", "command": "echo"},
            ],
        )

        errors = runner.validate_workflow(workflow)

        assert len(errors) == 1
        assert "No executor registered" in errors[0]

    def test_validate_circular_dependency(self, runner: WorkflowRunner) -> None:
        """Test validation catches circular dependency."""

        @ExecutorRegistry.register("shell")
        class DummyExecutor(NodeExecutor):
            async def execute(self, node: BaseNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

        workflow = Workflow(
            name="circular",
            nodes=[
                {"type": "shell", "id": "a", "command": "echo", "depends_on": ["b"]},
                {"type": "shell", "id": "b", "command": "echo", "depends_on": ["a"]},
            ],
        )

        errors = runner.validate_workflow(workflow)

        assert any("Circular dependency" in e for e in errors)

    def test_validate_clean_workflow(self, runner: WorkflowRunner) -> None:
        """Test validation passes for clean workflow."""

        @ExecutorRegistry.register("shell")
        class DummyExecutor(NodeExecutor):
            async def execute(self, node: BaseNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

        workflow = Workflow(
            name="clean",
            nodes=[
                {"type": "shell", "id": "a", "command": "echo"},
                {"type": "shell", "id": "b", "command": "echo", "depends_on": ["a"]},
            ],
        )

        errors = runner.validate_workflow(workflow)

        assert len(errors) == 0


class TestWorkflowRunnerTemplating:
    """Tests for template rendering in runner."""

    def setup_method(self) -> None:
        """Clear registry and register test executor."""
        ExecutorRegistry.clear()

        @ExecutorRegistry.register("shell")
        class CapturingExecutor(NodeExecutor):
            """Executor that captures the rendered command."""

            async def execute(self, node: BaseNode, context: ExecutionContext) -> NodeResult:
                if isinstance(node, ShellNode):
                    return NodeResult.success(
                        stdout=node.command,  # Return rendered command
                        output=node.command,
                    )
                return NodeResult.error("Not a shell node")

    @pytest.fixture
    def runner(self) -> WorkflowRunner:
        """Create a workflow runner."""
        return WorkflowRunner()

    @pytest.mark.asyncio
    async def test_template_rendering_with_inputs(self, runner: WorkflowRunner) -> None:
        """Test templates are rendered with inputs."""
        workflow = Workflow(
            name="template-inputs",
            inputs={
                "name": {"type": "string", "default": "World"},
            },
            nodes=[
                {
                    "type": "shell",
                    "id": "greet",
                    "command": "echo Hello {{ inputs.name }}",
                },
            ],
        )

        context = await runner.run(workflow)

        assert context.status == "success"
        # The captured command should be rendered
        assert context.nodes["greet"].stdout == "echo Hello World"

    @pytest.mark.asyncio
    async def test_template_rendering_with_node_outputs(self, runner: WorkflowRunner) -> None:
        """Test templates can reference previous node outputs."""
        workflow = Workflow(
            name="template-nodes",
            nodes=[
                {"type": "shell", "id": "step-1", "command": "first output"},
                {
                    "type": "shell",
                    "id": "step-2",
                    "command": "Previous: {{ nodes.step_1.output }}",
                    "depends_on": ["step-1"],
                },
            ],
        )

        context = await runner.run(workflow)

        assert context.status == "success"
        assert context.nodes["step-2"].stdout == "Previous: first output"

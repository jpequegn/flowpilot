"""Tests for FlowPilot node executor framework."""

import asyncio

import pytest

from flowpilot.engine import ExecutionContext, ExecutorRegistry, NodeExecutor, NodeResult
from flowpilot.models import ShellNode


class TestNodeResult:
    """Additional tests for NodeResult via executor."""

    def test_result_data_default(self) -> None:
        """Test result data field defaults to empty dict."""
        result = NodeResult.success()
        assert result.data == {}

    def test_result_with_data(self) -> None:
        """Test result with custom data."""
        result = NodeResult.success(data={"response_code": 200})
        assert result.data["response_code"] == 200


class TestExecutorRegistry:
    """Tests for ExecutorRegistry class."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        ExecutorRegistry.clear()

    def test_register_executor(self) -> None:
        """Test registering an executor."""

        @ExecutorRegistry.register("test-type")
        class TestExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

        assert ExecutorRegistry.has_executor("test-type")

    def test_get_executor(self) -> None:
        """Test getting registered executor."""

        @ExecutorRegistry.register("test-type")
        class TestExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success(stdout="executed")

        executor = ExecutorRegistry.get("test-type")
        assert executor is not None
        assert isinstance(executor, TestExecutor)

    def test_get_executor_returns_same_instance(self) -> None:
        """Test that get returns the same instance (caching)."""

        @ExecutorRegistry.register("cached-type")
        class CachedExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

        executor1 = ExecutorRegistry.get("cached-type")
        executor2 = ExecutorRegistry.get("cached-type")
        assert executor1 is executor2

    def test_get_unregistered_executor_raises(self) -> None:
        """Test getting unregistered executor raises error."""
        with pytest.raises(ValueError, match="No executor registered"):
            ExecutorRegistry.get("nonexistent")

    def test_has_executor(self) -> None:
        """Test has_executor check."""

        @ExecutorRegistry.register("exists")
        class ExistsExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

        assert ExecutorRegistry.has_executor("exists")
        assert not ExecutorRegistry.has_executor("does-not-exist")

    def test_clear_registry(self) -> None:
        """Test clearing the registry."""

        @ExecutorRegistry.register("to-clear")
        class ToClearExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                return NodeResult.success()

        assert ExecutorRegistry.has_executor("to-clear")

        ExecutorRegistry.clear()
        assert not ExecutorRegistry.has_executor("to-clear")


class TestNodeExecutor:
    """Tests for NodeExecutor base class."""

    def setup_method(self) -> None:
        """Clear registry before each test."""
        ExecutorRegistry.clear()

    @pytest.mark.asyncio
    async def test_execute_with_timeout_success(self) -> None:
        """Test execute_with_timeout completes successfully."""

        @ExecutorRegistry.register("fast")
        class FastExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                await asyncio.sleep(0.01)  # 10ms
                return NodeResult.success(stdout="fast")

        executor = ExecutorRegistry.get("fast")
        node = ShellNode(type="shell", id="test", command="echo")
        context = ExecutionContext(workflow_name="test")

        result = await executor.execute_with_timeout(node, context, timeout=1)
        assert result.status == "success"
        assert result.stdout == "fast"

    @pytest.mark.asyncio
    async def test_execute_with_timeout_times_out(self) -> None:
        """Test execute_with_timeout handles timeout."""

        @ExecutorRegistry.register("slow")
        class SlowExecutor(NodeExecutor):
            async def execute(self, node: ShellNode, context: ExecutionContext) -> NodeResult:
                await asyncio.sleep(10)  # 10 seconds
                return NodeResult.success()

        executor = ExecutorRegistry.get("slow")
        node = ShellNode(type="shell", id="test", command="echo")
        context = ExecutionContext(workflow_name="test")

        result = await executor.execute_with_timeout(node, context, timeout=0.1)
        assert result.status == "error"
        assert result.error_message is not None
        assert "timed out" in result.error_message.lower()


class TestGetNodeTimeout:
    """Tests for get_node_timeout function."""

    def test_shell_node_timeout(self) -> None:
        """Test getting timeout from shell node."""
        from flowpilot.engine import get_node_timeout

        node = ShellNode(type="shell", id="test", command="echo", timeout=120)
        assert get_node_timeout(node) == 120

    def test_shell_node_default_timeout(self) -> None:
        """Test shell node default timeout."""
        from flowpilot.engine import get_node_timeout

        node = ShellNode(type="shell", id="test", command="echo")
        assert get_node_timeout(node) == 60

    def test_file_node_timeout(self) -> None:
        """Test file node gets default timeout."""
        from flowpilot.engine import get_node_timeout
        from flowpilot.models import FileReadNode

        node = FileReadNode(type="file-read", id="test", path="/tmp/file")
        assert get_node_timeout(node) == 30

    def test_condition_node_timeout(self) -> None:
        """Test condition node gets control flow timeout."""
        from flowpilot.engine import get_node_timeout
        from flowpilot.models import ConditionNode

        node = ConditionNode(
            type="condition",
            id="test",
            **{"if": "true", "then": "next"},
        )
        assert get_node_timeout(node) == 300

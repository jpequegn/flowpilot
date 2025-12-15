"""Tests for parallel node executor."""

from __future__ import annotations

import asyncio

import pytest

from flowpilot.engine.context import ExecutionContext, NodeResult
from flowpilot.engine.executor import ExecutorRegistry
from flowpilot.engine.nodes.parallel import ParallelExecutor
from flowpilot.models import ParallelNode


class TestParallelNodeModel:
    """Tests for ParallelNode model."""

    def test_create_parallel_node(self) -> None:
        """Test creating a basic parallel node."""
        node = ParallelNode(
            id="test-parallel",
            type="parallel",
            nodes=["task-a", "task-b", "task-c"],
        )
        assert node.id == "test-parallel"
        assert node.type == "parallel"
        assert node.nodes == ["task-a", "task-b", "task-c"]
        assert node.fail_fast is True
        assert node.max_concurrency is None
        assert node.timeout is None

    def test_parallel_node_with_all_options(self) -> None:
        """Test parallel node with all options specified."""
        node = ParallelNode(
            id="full-parallel",
            type="parallel",
            nodes=["task-a", "task-b"],
            fail_fast=False,
            max_concurrency=2,
            timeout=60,
        )
        assert node.fail_fast is False
        assert node.max_concurrency == 2
        assert node.timeout == 60

    def test_parallel_node_validation(self) -> None:
        """Test parallel node validation."""
        # max_concurrency must be >= 1
        with pytest.raises(ValueError):
            ParallelNode(
                id="invalid",
                type="parallel",
                nodes=["task-a"],
                max_concurrency=0,
            )

        # timeout must be >= 1
        with pytest.raises(ValueError):
            ParallelNode(
                id="invalid",
                type="parallel",
                nodes=["task-a"],
                timeout=0,
            )


class TestParallelExecutor:
    """Tests for ParallelExecutor class."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure ParallelExecutor is registered."""
        if not ExecutorRegistry.has_executor("parallel"):
            ExecutorRegistry.register("parallel")(ParallelExecutor)

    def test_executor_registered(self) -> None:
        """Test ParallelExecutor is registered."""
        if not ExecutorRegistry.has_executor("parallel"):
            ExecutorRegistry.register("parallel")(ParallelExecutor)
        assert ExecutorRegistry.has_executor("parallel")
        executor = ExecutorRegistry.get("parallel")
        assert isinstance(executor, ParallelExecutor)

    @pytest.mark.asyncio
    async def test_parallel_basic(self) -> None:
        """Test basic parallel execution."""
        node = ParallelNode(
            id="test-parallel",
            type="parallel",
            nodes=["task-a", "task-b", "task-c"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["parallel_nodes"] == ["task-a", "task-b", "task-c"]
        assert result.data["fail_fast"] is True
        assert result.data["node_count"] == 3

    @pytest.mark.asyncio
    async def test_parallel_empty_nodes(self) -> None:
        """Test parallel node with empty nodes list."""
        node = ParallelNode(
            id="empty-parallel",
            type="parallel",
            nodes=[],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["empty_parallel"] is True

    @pytest.mark.asyncio
    async def test_parallel_with_concurrency_limit(self) -> None:
        """Test parallel node with concurrency limit."""
        node = ParallelNode(
            id="limited-parallel",
            type="parallel",
            nodes=["task-a", "task-b", "task-c", "task-d"],
            max_concurrency=2,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["max_concurrency"] == 2

    @pytest.mark.asyncio
    async def test_parallel_fail_fast_mode(self) -> None:
        """Test parallel node fail-fast mode."""
        node = ParallelNode(
            id="fail-fast-parallel",
            type="parallel",
            nodes=["task-a", "task-b"],
            fail_fast=True,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["fail_fast"] is True

    @pytest.mark.asyncio
    async def test_parallel_wait_all_mode(self) -> None:
        """Test parallel node wait-all mode."""
        node = ParallelNode(
            id="wait-all-parallel",
            type="parallel",
            nodes=["task-a", "task-b"],
            fail_fast=False,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["fail_fast"] is False

    @pytest.mark.asyncio
    async def test_parallel_with_timeout(self) -> None:
        """Test parallel node with timeout."""
        node = ParallelNode(
            id="timeout-parallel",
            type="parallel",
            nodes=["task-a"],
            timeout=30,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["timeout"] == 30


class TestParallelConcurrency:
    """Tests for parallel concurrency behavior."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self) -> None:
        """Test that semaphore properly limits concurrency."""
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def track_concurrency() -> int:
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent

            await asyncio.sleep(0.05)  # Simulate work

            async with lock:
                current_concurrent -= 1

            return max_concurrent

        # Create semaphore with limit of 2
        semaphore = asyncio.Semaphore(2)

        async def limited_task() -> int:
            async with semaphore:
                return await track_concurrency()

        # Run 5 tasks with concurrency limit of 2
        tasks = [limited_task() for _ in range(5)]
        await asyncio.gather(*tasks)

        # Max concurrent should be at most 2
        assert max_concurrent <= 2


class TestParallelIntegration:
    """Integration tests for parallel execution."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure executors are registered."""
        if not ExecutorRegistry.has_executor("parallel"):
            ExecutorRegistry.register("parallel")(ParallelExecutor)

    @pytest.mark.asyncio
    async def test_parallel_all_options(self) -> None:
        """Test parallel node with all options."""
        node = ParallelNode(
            id="full-options-parallel",
            type="parallel",
            nodes=["task-a", "task-b", "task-c"],
            fail_fast=False,
            max_concurrency=2,
            timeout=120,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"key": "value"},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["parallel_nodes"] == ["task-a", "task-b", "task-c"]
        assert result.data["max_concurrency"] == 2
        assert result.data["fail_fast"] is False
        assert result.data["timeout"] == 120
        assert result.data["node_count"] == 3

    @pytest.mark.asyncio
    async def test_parallel_node_result_format(self) -> None:
        """Test parallel node result format."""
        node = ParallelNode(
            id="result-format-parallel",
            type="parallel",
            nodes=["node-1", "node-2"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = ParallelExecutor()
        result = await executor.execute(node, context)

        # Check result structure
        assert result.status in ["success", "error"]
        assert "parallel_nodes" in result.data
        assert "fail_fast" in result.data
        assert "timeout" in result.data
        assert "max_concurrency" in result.data
        assert result.duration_ms >= 0
        assert result.started_at is not None
        assert result.finished_at is not None


class TestParallelNodeResultStorage:
    """Tests for parallel node result storage in context."""

    def test_node_results_stored(self) -> None:
        """Test that parallel child node results are stored in context."""
        context = ExecutionContext(workflow_name="test")

        # Simulate storing results from parallel execution
        context.set_node_result("task-a", NodeResult.success(stdout="A"))
        context.set_node_result("task-b", NodeResult.success(stdout="B"))

        result_a = context.get_node_result("task-a")
        result_b = context.get_node_result("task-b")

        assert result_a is not None
        assert result_a.stdout == "A"
        assert result_b is not None
        assert result_b.stdout == "B"

    def test_parallel_results_in_template_context(self) -> None:
        """Test parallel results are accessible in template context."""
        context = ExecutionContext(workflow_name="test")

        context.set_node_result("task-a", NodeResult.success(output={"count": 10}))
        context.set_node_result("task-b", NodeResult.success(output={"count": 20}))

        template_ctx = context.get_template_context()

        # Node IDs with hyphens are converted to underscores
        assert template_ctx["nodes"]["task_a"]["output"] == {"count": 10}
        assert template_ctx["nodes"]["task_b"]["output"] == {"count": 20}

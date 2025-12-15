"""Tests for loop node executor."""

from __future__ import annotations

import pytest

from flowpilot.engine.context import ExecutionContext, NodeResult
from flowpilot.engine.executor import ExecutorRegistry
from flowpilot.engine.nodes.loop import LoopExecutor
from flowpilot.models import LoopNode


class TestLoopNodeModel:
    """Tests for LoopNode model."""

    def test_create_loop_node(self) -> None:
        """Test creating a basic loop node."""
        node = LoopNode(
            id="test-loop",
            type="loop",
            for_each="inputs.items",
            do=["process-item"],
        )
        assert node.id == "test-loop"
        assert node.type == "loop"
        assert node.for_each == "inputs.items"
        assert node.as_var == "item"
        assert node.index_var == "index"
        assert node.do == ["process-item"]
        assert node.max_iterations is None
        assert node.break_if is None

    def test_loop_node_with_all_options(self) -> None:
        """Test loop node with all options specified."""
        node = LoopNode(
            id="full-loop",
            type="loop",
            for_each="inputs.files",
            as_var="file",
            index_var="i",
            do=["read-file", "process-file"],
            max_iterations=100,
            break_if="file == 'stop.txt'",
        )
        assert node.as_var == "file"
        assert node.index_var == "i"
        assert node.do == ["read-file", "process-file"]
        assert node.max_iterations == 100
        assert node.break_if == "file == 'stop.txt'"

    def test_loop_node_with_alias(self) -> None:
        """Test loop node using 'for' alias."""
        data = {
            "id": "alias-loop",
            "type": "loop",
            "for": "inputs.list",
            "as": "element",
            "do": ["process"],
        }
        node = LoopNode.model_validate(data)
        assert node.for_each == "inputs.list"
        assert node.as_var == "element"


class TestLoopExecutor:
    """Tests for LoopExecutor class."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure LoopExecutor is registered."""
        # Re-register the executor in case it was cleared by other tests
        if not ExecutorRegistry.has_executor("loop"):
            ExecutorRegistry.register("loop")(LoopExecutor)

    def test_executor_registered(self) -> None:
        """Test LoopExecutor is registered."""
        # Ensure registration before test
        if not ExecutorRegistry.has_executor("loop"):
            ExecutorRegistry.register("loop")(LoopExecutor)
        assert ExecutorRegistry.has_executor("loop")
        executor = ExecutorRegistry.get("loop")
        assert isinstance(executor, LoopExecutor)

    @pytest.mark.asyncio
    async def test_loop_over_list(self) -> None:
        """Test looping over a list."""
        node = LoopNode(
            id="test-loop",
            type="loop",
            for_each="inputs.items",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": [1, 2, 3]},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["iterations_planned"] == 3
        assert result.data["loop_items"] == [1, 2, 3]
        assert result.data["as_var"] == "item"
        assert result.data["index_var"] == "index"

    @pytest.mark.asyncio
    async def test_loop_empty_list(self) -> None:
        """Test looping over empty list."""
        node = LoopNode(
            id="empty-loop",
            type="loop",
            for_each="inputs.items",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": []},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["iterations"] == 0
        assert result.data["total_items"] == 0

    @pytest.mark.asyncio
    async def test_loop_max_iterations(self) -> None:
        """Test max_iterations limit."""
        node = LoopNode(
            id="limited-loop",
            type="loop",
            for_each="inputs.items",
            do=["process"],
            max_iterations=2,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": [1, 2, 3, 4, 5]},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["iterations_planned"] == 2
        assert result.data["total_items"] == 5
        assert result.data["loop_items"] == [1, 2]

    @pytest.mark.asyncio
    async def test_loop_non_list_error(self) -> None:
        """Test error when for_each resolves to non-list."""
        node = LoopNode(
            id="bad-loop",
            type="loop",
            for_each="inputs['value']",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"value": "not a list"},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert "must resolve to a list" in result.error_message

    @pytest.mark.asyncio
    async def test_loop_none_expression_error(self) -> None:
        """Test error when for_each resolves to None."""
        node = LoopNode(
            id="none-loop",
            type="loop",
            for_each="inputs.missing",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "error"

    @pytest.mark.asyncio
    async def test_loop_tuple_support(self) -> None:
        """Test looping over tuple."""
        node = LoopNode(
            id="tuple-loop",
            type="loop",
            for_each="inputs.items",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": (1, 2, 3)},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["iterations_planned"] == 3

    @pytest.mark.asyncio
    async def test_loop_with_node_results(self) -> None:
        """Test loop with access to previous node results."""
        node = LoopNode(
            id="results-loop",
            type="loop",
            for_each="nodes.get_items.data.items",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )
        # Add previous node result
        context.set_node_result(
            "get-items",
            NodeResult(
                status="success",
                data={"items": ["a", "b", "c"]},
            ),
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["loop_items"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_loop_with_range(self) -> None:
        """Test loop using range function."""
        node = LoopNode(
            id="range-loop",
            type="loop",
            for_each="list(range(5))",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["loop_items"] == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_loop_invalid_expression(self) -> None:
        """Test error on invalid expression syntax."""
        node = LoopNode(
            id="syntax-error-loop",
            type="loop",
            for_each="this is not valid python",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert "Invalid syntax" in result.error_message

    @pytest.mark.asyncio
    async def test_loop_disallowed_name(self) -> None:
        """Test error on disallowed names in expression."""
        node = LoopNode(
            id="unsafe-loop",
            type="loop",
            for_each="__import__('os').listdir('.')",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert "not allowed" in result.error_message


class TestLoopExecutorBreakCondition:
    """Tests for break condition evaluation."""

    def test_break_condition_true(self) -> None:
        """Test break condition evaluates to True."""
        executor = LoopExecutor()
        context = {"item": "stop", "index": 5}

        result = executor._evaluate_break_condition("item == 'stop'", context)
        assert result is True

    def test_break_condition_false(self) -> None:
        """Test break condition evaluates to False."""
        executor = LoopExecutor()
        context = {"item": "continue", "index": 2}

        result = executor._evaluate_break_condition("item == 'stop'", context)
        assert result is False

    def test_break_condition_index(self) -> None:
        """Test break condition using index."""
        executor = LoopExecutor()
        context = {"item": "value", "index": 10}

        result = executor._evaluate_break_condition("index >= 10", context)
        assert result is True

    def test_break_condition_invalid_syntax(self) -> None:
        """Test invalid syntax returns False."""
        executor = LoopExecutor()
        context = {"item": "value"}

        result = executor._evaluate_break_condition("this is bad syntax!!!", context)
        assert result is False

    def test_break_condition_disallowed_name(self) -> None:
        """Test disallowed name returns False."""
        executor = LoopExecutor()
        context = {"item": "value"}

        result = executor._evaluate_break_condition("os.path.exists('/')", context)
        assert result is False


class TestExecutionContextLoopVariables:
    """Tests for loop variable management in ExecutionContext."""

    def test_set_loop_variable(self) -> None:
        """Test setting a loop variable."""
        context = ExecutionContext(workflow_name="test")

        context.set_loop_variable("item", "value")
        context.set_loop_variable("index", 5)

        assert context.loop_variables["item"] == "value"
        assert context.loop_variables["index"] == 5

    def test_loop_variables_in_template_context(self) -> None:
        """Test loop variables appear in template context."""
        context = ExecutionContext(workflow_name="test")
        context.set_loop_variable("item", {"name": "test"})
        context.set_loop_variable("index", 3)

        template_ctx = context.get_template_context()

        assert template_ctx["item"] == {"name": "test"}
        assert template_ctx["index"] == 3

    def test_clear_specific_loop_variables(self) -> None:
        """Test clearing specific loop variables."""
        context = ExecutionContext(workflow_name="test")
        context.set_loop_variable("item", "value")
        context.set_loop_variable("index", 5)
        context.set_loop_variable("extra", "data")

        context.clear_loop_variables("item", "index")

        assert "item" not in context.loop_variables
        assert "index" not in context.loop_variables
        assert context.loop_variables["extra"] == "data"

    def test_clear_all_loop_variables(self) -> None:
        """Test clearing all loop variables."""
        context = ExecutionContext(workflow_name="test")
        context.set_loop_variable("item", "value")
        context.set_loop_variable("index", 5)

        context.clear_loop_variables()

        assert len(context.loop_variables) == 0

    def test_clear_nonexistent_variable(self) -> None:
        """Test clearing non-existent variable doesn't error."""
        context = ExecutionContext(workflow_name="test")
        context.set_loop_variable("item", "value")

        # Should not raise
        context.clear_loop_variables("nonexistent", "item")

        assert "item" not in context.loop_variables


class TestLoopExecutorExpressionResolution:
    """Tests for expression resolution."""

    @pytest.mark.asyncio
    async def test_nested_dict_access(self) -> None:
        """Test accessing nested dictionary values."""
        node = LoopNode(
            id="nested-loop",
            type="loop",
            for_each="inputs.data.items",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"data": {"items": [1, 2, 3]}},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["loop_items"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_list_comprehension(self) -> None:
        """Test list comprehension in expression."""
        node = LoopNode(
            id="comprehension-loop",
            type="loop",
            for_each="[x * 2 for x in inputs.items]",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": [1, 2, 3]},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["loop_items"] == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_env_access(self) -> None:
        """Test accessing environment variables."""
        import os

        os.environ["TEST_LOOP_VAR"] = "test_value"

        node = LoopNode(
            id="env-loop",
            type="loop",
            for_each="list(env.keys())[:3]",
            do=["process"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["iterations_planned"] == 3


class TestLoopNodeIntegration:
    """Integration tests for loop nodes."""

    @pytest.mark.asyncio
    async def test_loop_with_objects(self) -> None:
        """Test looping over list of objects."""
        node = LoopNode(
            id="object-loop",
            type="loop",
            for_each="inputs.users",
            as_var="user",
            do=["greet-user"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={
                "users": [
                    {"name": "Alice", "age": 30},
                    {"name": "Bob", "age": 25},
                ]
            },
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["as_var"] == "user"
        assert result.data["loop_items"] == [
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 25},
        ]

    @pytest.mark.asyncio
    async def test_loop_multiple_child_nodes(self) -> None:
        """Test loop with multiple child nodes."""
        node = LoopNode(
            id="multi-child-loop",
            type="loop",
            for_each="inputs.items",
            do=["step-1", "step-2", "step-3"],
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": ["a", "b"]},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["child_nodes"] == ["step-1", "step-2", "step-3"]

    @pytest.mark.asyncio
    async def test_loop_break_if_provided(self) -> None:
        """Test loop with break_if condition."""
        node = LoopNode(
            id="break-loop",
            type="loop",
            for_each="inputs.items",
            do=["process"],
            break_if="item == 'stop'",
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"items": ["a", "b", "stop", "c"]},
        )

        executor = LoopExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["break_if"] == "item == 'stop'"
        # The executor returns all items; the runner handles break_if
        assert len(result.data["loop_items"]) == 4

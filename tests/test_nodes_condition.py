"""Tests for condition node executor."""

import pytest

from flowpilot.engine import ExecutionContext
from flowpilot.engine.nodes import ConditionExecutor
from flowpilot.models import ConditionNode


@pytest.fixture
def executor() -> ConditionExecutor:
    """Create a condition executor instance."""
    return ConditionExecutor()


@pytest.fixture
def context() -> ExecutionContext:
    """Create an execution context."""
    return ExecutionContext(workflow_name="test")


class TestConditionExecutor:
    """Tests for ConditionExecutor."""

    @pytest.mark.asyncio
    async def test_simple_true_condition(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test a simple True condition."""
        node = ConditionNode(
            type="condition",
            id="true-test",
            if_expr="True",
            then="then-node",
            else_node="else-node",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "True"
        assert result.data["result"] is True
        assert result.data["next_node"] == "then-node"
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_simple_false_condition(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test a simple False condition."""
        node = ConditionNode(
            type="condition",
            id="false-test",
            if_expr="False",
            then="then-node",
            else_node="else-node",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "False"
        assert result.data["result"] is False
        assert result.data["next_node"] == "else-node"

    @pytest.mark.asyncio
    async def test_comparison_greater_than(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test greater than comparison."""
        node = ConditionNode(
            type="condition",
            id="gt-test",
            if_expr="10 > 5",
            then="greater",
            else_node="not-greater",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True
        assert result.data["next_node"] == "greater"

    @pytest.mark.asyncio
    async def test_comparison_less_than(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test less than comparison."""
        node = ConditionNode(
            type="condition",
            id="lt-test",
            if_expr="3 < 5",
            then="less",
            else_node="not-less",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True
        assert result.data["next_node"] == "less"

    @pytest.mark.asyncio
    async def test_comparison_equality(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test equality comparison."""
        node = ConditionNode(
            type="condition",
            id="eq-test",
            if_expr="5 == 5",
            then="equal",
            else_node="not-equal",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True
        assert result.data["next_node"] == "equal"

    @pytest.mark.asyncio
    async def test_string_comparison(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test string comparison."""
        node = ConditionNode(
            type="condition",
            id="string-test",
            if_expr="'hello' == 'hello'",
            then="match",
            else_node="no-match",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_len_function(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test len() function is allowed."""
        node = ConditionNode(
            type="condition",
            id="len-test",
            if_expr="len('hello') == 5",
            then="correct",
            else_node="wrong",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_list_operations(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test list operations are allowed."""
        node = ConditionNode(
            type="condition",
            id="list-test",
            if_expr="len([1, 2, 3]) > 2",
            then="valid",
            else_node="invalid",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_any_all_functions(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test any() and all() functions are allowed."""
        # Test any()
        node = ConditionNode(
            type="condition",
            id="any-test",
            if_expr="any([False, True, False])",
            then="has-true",
            else_node="all-false",
        )
        result = await executor.execute(node, context)
        assert result.data["result"] is True

        # Test all()
        node = ConditionNode(
            type="condition",
            id="all-test",
            if_expr="all([True, True, True])",
            then="all-true",
            else_node="has-false",
        )
        result = await executor.execute(node, context)
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_min_max_sum_functions(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test min(), max(), sum() functions are allowed."""
        node = ConditionNode(
            type="condition",
            id="math-test",
            if_expr="sum([1, 2, 3]) == 6 and min([1, 2, 3]) == 1 and max([1, 2, 3]) == 3",
            then="correct",
            else_node="wrong",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_type_conversion_functions(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test type conversion functions are allowed."""
        node = ConditionNode(
            type="condition",
            id="type-test",
            if_expr="int('42') == 42 and str(42) == '42' and float('3.14') > 3",
            then="correct",
            else_node="wrong",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_bool_function(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test bool() function is allowed."""
        node = ConditionNode(
            type="condition",
            id="bool-test",
            if_expr="bool(1) and not bool(0)",
            then="correct",
            else_node="wrong",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_abs_function(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test abs() function is allowed."""
        node = ConditionNode(
            type="condition",
            id="abs-test",
            if_expr="abs(-5) == 5",
            then="correct",
            else_node="wrong",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_none_comparison(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test None comparison is allowed."""
        node = ConditionNode(
            type="condition",
            id="none-test",
            if_expr="None is None",
            then="is-none",
            else_node="not-none",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_context_variable_access(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test accessing context variables."""
        # Add a node result to context
        from flowpilot.engine.context import NodeResult

        context.set_node_result(
            "previous",
            NodeResult.success(output="42", data={"value": 42}),
        )

        node = ConditionNode(
            type="condition",
            id="context-test",
            if_expr="nodes['previous']['output'] == '42'",
            then="match",
            else_node="no-match",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_context_data_access(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test accessing data from previous node."""
        from flowpilot.engine.context import NodeResult

        # Note: node IDs with hyphens are converted to underscores in template context
        context.set_node_result(
            "api-call",
            NodeResult.success(
                output="response",
                data={"status_code": 200, "body": {"success": True}},
            ),
        )

        node = ConditionNode(
            type="condition",
            id="data-test",
            if_expr="nodes['api_call']['data']['status_code'] == 200",
            then="success",
            else_node="failure",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True
        assert result.data["next_node"] == "success"

    @pytest.mark.asyncio
    async def test_disallowed_name_import(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test that import is disallowed."""
        node = ConditionNode(
            type="condition",
            id="import-test",
            if_expr="__import__('os').system('ls')",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "not allowed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_disallowed_name_open(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test that open is disallowed."""
        node = ConditionNode(
            type="condition",
            id="open-test",
            if_expr="open('/etc/passwd')",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "not allowed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_disallowed_name_eval(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test that eval is disallowed."""
        node = ConditionNode(
            type="condition",
            id="eval-test",
            if_expr="eval('1+1')",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "not allowed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_disallowed_name_exec(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test that exec is disallowed."""
        node = ConditionNode(
            type="condition",
            id="exec-test",
            if_expr="exec('x=1')",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "not allowed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_syntax_error(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test handling of syntax errors."""
        node = ConditionNode(
            type="condition",
            id="syntax-test",
            if_expr="if True then 1",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "syntax" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_runtime_error(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test handling of runtime errors."""
        node = ConditionNode(
            type="condition",
            id="runtime-test",
            if_expr="1 / 0",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_undefined_variable(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test accessing undefined variable."""
        node = ConditionNode(
            type="condition",
            id="undefined-test",
            if_expr="undefined_var == 1",
            then="should-fail",
            else_node="should-fail",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "not allowed" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_complex_boolean_expression(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test complex boolean expressions."""
        node = ConditionNode(
            type="condition",
            id="complex-test",
            if_expr="(5 > 3 and 10 < 20) or (1 == 2)",
            then="valid",
            else_node="invalid",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_in_operator(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test 'in' operator."""
        node = ConditionNode(
            type="condition",
            id="in-test",
            if_expr="'hello' in 'hello world'",
            then="found",
            else_node="not-found",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_list_membership(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test list membership check."""
        node = ConditionNode(
            type="condition",
            id="membership-test",
            if_expr="3 in [1, 2, 3, 4, 5]",
            then="found",
            else_node="not-found",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["result"] is True

    @pytest.mark.asyncio
    async def test_condition_stores_expression(
        self, executor: ConditionExecutor, context: ExecutionContext
    ) -> None:
        """Test that the original expression is stored in result."""
        node = ConditionNode(
            type="condition",
            id="expr-test",
            if_expr="10 >= 5",
            then="yes",
            else_node="no",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["condition"] == "10 >= 5"


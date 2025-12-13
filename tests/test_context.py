"""Tests for FlowPilot execution context."""

from datetime import datetime, timedelta

from flowpilot.engine import ExecutionContext, NodeResult


class TestNodeResult:
    """Tests for NodeResult dataclass."""

    def test_pending_result(self) -> None:
        """Test creating pending result."""
        result = NodeResult.pending()
        assert result.status == "pending"
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.output is None
        assert result.error_message is None

    def test_running_result(self) -> None:
        """Test creating running result."""
        result = NodeResult.running()
        assert result.status == "running"
        assert result.started_at is not None

    def test_success_result(self) -> None:
        """Test creating success result."""
        started = datetime.now() - timedelta(seconds=1)
        result = NodeResult.success(
            stdout="hello",
            stderr="",
            output={"key": "value"},
            data={"extra": "data"},
            started_at=started,
        )
        assert result.status == "success"
        assert result.stdout == "hello"
        assert result.output == {"key": "value"}
        assert result.data == {"extra": "data"}
        assert result.duration_ms >= 1000
        assert result.finished_at is not None

    def test_error_result(self) -> None:
        """Test creating error result."""
        started = datetime.now()
        result = NodeResult.error(
            "Something went wrong",
            stdout="partial output",
            stderr="error details",
            started_at=started,
        )
        assert result.status == "error"
        assert result.error_message == "Something went wrong"
        assert result.stdout == "partial output"
        assert result.stderr == "error details"

    def test_skipped_result(self) -> None:
        """Test creating skipped result."""
        result = NodeResult.skipped("Condition not met")
        assert result.status == "skipped"
        assert result.error_message == "Condition not met"

    def test_skipped_result_no_reason(self) -> None:
        """Test creating skipped result without reason."""
        result = NodeResult.skipped()
        assert result.status == "skipped"
        assert result.error_message is None


class TestExecutionContext:
    """Tests for ExecutionContext dataclass."""

    def test_create_context(self) -> None:
        """Test creating execution context."""
        context = ExecutionContext(
            workflow_name="test-workflow",
            inputs={"greeting": "hello"},
        )
        assert context.workflow_name == "test-workflow"
        assert context.inputs == {"greeting": "hello"}
        assert context.execution_id is not None
        assert context.status == "running"
        assert len(context.nodes) == 0

    def test_set_node_result(self) -> None:
        """Test setting node result."""
        context = ExecutionContext(workflow_name="test")
        result = NodeResult.success(stdout="output")
        context.set_node_result("node-1", result)

        assert "node-1" in context.nodes
        assert context.nodes["node-1"].stdout == "output"

    def test_get_node_result(self) -> None:
        """Test getting node result."""
        context = ExecutionContext(workflow_name="test")
        result = NodeResult.success(stdout="output")
        context.set_node_result("node-1", result)

        retrieved = context.get_node_result("node-1")
        assert retrieved is not None
        assert retrieved.stdout == "output"

        missing = context.get_node_result("nonexistent")
        assert missing is None

    def test_mark_finished_success(self) -> None:
        """Test marking context as finished with success."""
        context = ExecutionContext(workflow_name="test")
        context.mark_finished("success")

        assert context.status == "success"
        assert context.finished_at is not None

    def test_mark_finished_error(self) -> None:
        """Test marking context as finished with error."""
        context = ExecutionContext(workflow_name="test")
        context.mark_finished("error")

        assert context.status == "error"
        assert context.finished_at is not None

    def test_has_errors(self) -> None:
        """Test checking for errors."""
        context = ExecutionContext(workflow_name="test")
        assert not context.has_errors

        context.set_node_result("node-1", NodeResult.success())
        assert not context.has_errors

        context.set_node_result("node-2", NodeResult.error("failed"))
        assert context.has_errors

    def test_duration_ms(self) -> None:
        """Test duration calculation."""
        context = ExecutionContext(workflow_name="test")
        # Duration should be positive
        assert context.duration_ms >= 0

    def test_get_template_context(self) -> None:
        """Test getting template context."""
        context = ExecutionContext(
            workflow_name="test",
            execution_id="exec-123",
            inputs={"name": "World"},
        )
        context.set_node_result(
            "say-hello",
            NodeResult.success(stdout="Hello, World!", output="Hello, World!"),
        )

        tpl_ctx = context.get_template_context()

        assert tpl_ctx["inputs"] == {"name": "World"}
        assert tpl_ctx["execution_id"] == "exec-123"
        assert tpl_ctx["workflow_name"] == "test"
        assert "env" in tpl_ctx
        assert callable(tpl_ctx["date"])
        # Check node results (hyphens converted to underscores)
        assert "say_hello" in tpl_ctx["nodes"]
        assert tpl_ctx["nodes"]["say_hello"]["stdout"] == "Hello, World!"
        assert tpl_ctx["nodes"]["say_hello"]["output"] == "Hello, World!"

    def test_template_context_date_function(self) -> None:
        """Test date function in template context."""
        context = ExecutionContext(workflow_name="test")
        tpl_ctx = context.get_template_context()

        date_fn = tpl_ctx["date"]
        result = date_fn("%Y-%m-%d")
        assert len(result) == 10  # Format: YYYY-MM-DD

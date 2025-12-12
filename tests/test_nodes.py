"""Tests for FlowPilot node models."""

import pytest
from pydantic import ValidationError

from flowpilot.models import (
    ClaudeApiNode,
    ClaudeCliNode,
    ConditionNode,
    DelayNode,
    FileReadNode,
    FileWriteNode,
    HttpNode,
    LoopNode,
    ParallelNode,
    ShellNode,
)


class TestShellNode:
    """Tests for ShellNode model."""

    def test_minimal_shell_node(self) -> None:
        """Test shell node with minimal config."""
        node = ShellNode(type="shell", id="run-command", command="echo hello")
        assert node.id == "run-command"
        assert node.command == "echo hello"
        assert node.timeout == 60
        assert node.working_dir is None
        assert node.env == {}

    def test_full_shell_node(self) -> None:
        """Test shell node with all options."""
        node = ShellNode(
            type="shell",
            id="build",
            command="make build",
            working_dir="/project",
            env={"DEBUG": "1"},
            timeout=120,
            depends_on=["checkout"],
        )
        assert node.working_dir == "/project"
        assert node.env == {"DEBUG": "1"}
        assert node.timeout == 120
        assert node.depends_on == ["checkout"]

    def test_invalid_node_id(self) -> None:
        """Test invalid node ID format."""
        with pytest.raises(ValidationError) as exc_info:
            ShellNode(type="shell", id="Run Command", command="echo")
        assert "pattern" in str(exc_info.value).lower() or "string_pattern" in str(exc_info.value)

    def test_invalid_node_id_starts_with_number(self) -> None:
        """Test node ID cannot start with number."""
        with pytest.raises(ValidationError):
            ShellNode(type="shell", id="1-node", command="echo")

    def test_invalid_timeout(self) -> None:
        """Test timeout must be positive."""
        with pytest.raises(ValidationError):
            ShellNode(type="shell", id="node", command="echo", timeout=0)


class TestHttpNode:
    """Tests for HttpNode model."""

    def test_minimal_http_node(self) -> None:
        """Test HTTP node with minimal config."""
        node = HttpNode(type="http", id="fetch-data", url="https://api.example.com")
        assert node.method == "GET"
        assert node.headers == {}
        assert node.body is None
        assert node.timeout == 30

    def test_full_http_node(self) -> None:
        """Test HTTP node with all options."""
        node = HttpNode(
            type="http",
            id="post-data",
            url="https://api.example.com/data",
            method="POST",
            headers={"Authorization": "Bearer token", "Content-Type": "application/json"},
            body={"key": "value"},
            timeout=60,
        )
        assert node.method == "POST"
        assert "Authorization" in node.headers
        assert node.body == {"key": "value"}


class TestFileNodes:
    """Tests for FileReadNode and FileWriteNode."""

    def test_file_read_node(self) -> None:
        """Test file read node."""
        node = FileReadNode(type="file-read", id="read-config", path="./config.yaml")
        assert node.path == "./config.yaml"
        assert node.encoding == "utf-8"

    def test_file_read_custom_encoding(self) -> None:
        """Test file read with custom encoding."""
        node = FileReadNode(
            type="file-read", id="read-legacy", path="./data.txt", encoding="latin-1"
        )
        assert node.encoding == "latin-1"

    def test_file_write_node(self) -> None:
        """Test file write node."""
        node = FileWriteNode(
            type="file-write", id="write-report", path="./report.md", content="# Report"
        )
        assert node.path == "./report.md"
        assert node.content == "# Report"
        assert node.mode == "write"

    def test_file_write_append_mode(self) -> None:
        """Test file write in append mode."""
        node = FileWriteNode(
            type="file-write",
            id="append-log",
            path="./log.txt",
            content="New entry",
            mode="append",
        )
        assert node.mode == "append"


class TestConditionNode:
    """Tests for ConditionNode model."""

    def test_condition_node(self) -> None:
        """Test condition node with if/then/else."""
        node = ConditionNode(
            type="condition",
            id="check-result",
            **{"if": "'error' in output", "then": "handle-error", "else": "continue"},
        )
        assert node.if_expr == "'error' in output"
        assert node.then == "handle-error"
        assert node.else_node == "continue"

    def test_condition_node_no_else(self) -> None:
        """Test condition node without else."""
        node = ConditionNode(
            type="condition",
            id="check-only",
            **{"if": "result > 0", "then": "process"},
        )
        assert node.else_node is None


class TestLoopNode:
    """Tests for LoopNode model."""

    def test_loop_node(self) -> None:
        """Test loop node."""
        node = LoopNode(
            type="loop",
            id="process-items",
            **{"for": "items", "as": "item", "do": "process-item"},
        )
        assert node.for_each == "items"
        assert node.as_var == "item"
        assert node.do == "process-item"

    def test_loop_node_default_as(self) -> None:
        """Test loop node with default 'as' variable."""
        node = LoopNode(type="loop", id="iterate", **{"for": "data", "do": "handle"})
        assert node.as_var == "item"


class TestDelayNode:
    """Tests for DelayNode model."""

    def test_delay_node(self) -> None:
        """Test delay node."""
        node = DelayNode(type="delay", id="wait", duration="5s")
        assert node.duration == "5s"


class TestParallelNode:
    """Tests for ParallelNode model."""

    def test_parallel_node(self) -> None:
        """Test parallel node."""
        node = ParallelNode(
            type="parallel",
            id="parallel-tasks",
            nodes=["task-a", "task-b", "task-c"],
        )
        assert node.nodes == ["task-a", "task-b", "task-c"]
        assert node.fail_fast is True

    def test_parallel_node_no_fail_fast(self) -> None:
        """Test parallel node with fail_fast disabled."""
        node = ParallelNode(
            type="parallel",
            id="parallel-all",
            nodes=["a", "b"],
            fail_fast=False,
        )
        assert node.fail_fast is False


class TestClaudeCliNode:
    """Tests for ClaudeCliNode model."""

    def test_minimal_claude_cli_node(self) -> None:
        """Test Claude CLI node with minimal config."""
        node = ClaudeCliNode(type="claude-cli", id="ask-claude", prompt="Review code")
        assert node.prompt == "Review code"
        assert node.model is None
        assert node.working_dir is None
        assert node.timeout == 300
        assert node.output_format == "text"

    def test_full_claude_cli_node(self) -> None:
        """Test Claude CLI node with all options."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="analyze",
            prompt="Analyze this code",
            model="sonnet",
            working_dir="/project",
            timeout=600,
            output_format="json",
        )
        assert node.model == "sonnet"
        assert node.output_format == "json"


class TestClaudeApiNode:
    """Tests for ClaudeApiNode model."""

    def test_minimal_claude_api_node(self) -> None:
        """Test Claude API node with minimal config."""
        node = ClaudeApiNode(type="claude-api", id="api-call", prompt="Hello")
        assert node.prompt == "Hello"
        assert node.model == "claude-sonnet-4-20250514"
        assert node.system is None
        assert node.max_tokens == 4096
        assert node.temperature is None

    def test_full_claude_api_node(self) -> None:
        """Test Claude API node with all options."""
        node = ClaudeApiNode(
            type="claude-api",
            id="custom-call",
            prompt="Summarize",
            model="claude-3-haiku-20240307",
            system="Be concise",
            max_tokens=500,
            temperature=0.3,
            timeout=60,
            output_format="json",
        )
        assert node.model == "claude-3-haiku-20240307"
        assert node.system == "Be concise"
        assert node.temperature == 0.3

    def test_invalid_temperature(self) -> None:
        """Test temperature must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ClaudeApiNode(type="claude-api", id="node", prompt="test", temperature=1.5)

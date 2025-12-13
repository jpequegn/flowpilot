"""Tests for shell node executor."""

import os
import sys

import pytest

from flowpilot.engine import ExecutionContext
from flowpilot.engine.nodes import ShellExecutor
from flowpilot.models import ShellNode


@pytest.fixture
def executor() -> ShellExecutor:
    """Create a shell executor instance."""
    return ShellExecutor()


@pytest.fixture
def context() -> ExecutionContext:
    """Create an execution context."""
    return ExecutionContext(workflow_name="test")


class TestShellExecutor:
    """Tests for ShellExecutor."""

    @pytest.mark.asyncio
    async def test_execute_simple_command(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test executing a simple echo command."""
        node = ShellNode(type="shell", id="echo-test", command="echo hello")
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert "hello" in result.stdout
        assert result.output == "hello"
        assert result.data["exit_code"] == 0
        assert result.duration_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_command_with_stderr(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command that writes to stderr."""
        node = ShellNode(
            type="shell",
            id="stderr-test",
            command="echo error >&2",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert "error" in result.stderr

    @pytest.mark.asyncio
    async def test_execute_failing_command(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command with non-zero exit code."""
        node = ShellNode(type="shell", id="fail-test", command="exit 1")
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.data["exit_code"] == 1
        assert result.error_message is not None
        assert "exit" in result.error_message.lower() or "code" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_with_environment(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command with custom environment variables."""
        node = ShellNode(
            type="shell",
            id="env-test",
            command="echo $MY_VAR",
            env={"MY_VAR": "custom_value"},
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert "custom_value" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_with_working_directory(
        self, executor: ShellExecutor, context: ExecutionContext, tmp_path: str
    ) -> None:
        """Test command with working directory."""
        node = ShellNode(
            type="shell",
            id="cwd-test",
            command="pwd",
            working_dir=str(tmp_path),
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert str(tmp_path) in result.stdout

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command timeout."""
        node = ShellNode(
            type="shell",
            id="timeout-test",
            command="sleep 10",
            timeout=1,
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None
        assert "timed out" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_working_directory(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command with non-existent working directory."""
        node = ShellNode(
            type="shell",
            id="invalid-cwd-test",
            command="echo test",
            working_dir="/nonexistent/path/12345",
        )
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert result.error_message is not None

    @pytest.mark.asyncio
    async def test_execute_multiline_output(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command with multiline output."""
        node = ShellNode(
            type="shell",
            id="multiline-test",
            command="echo 'line1\nline2\nline3'",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert "line1" in result.stdout
        assert "line2" in result.stdout
        assert "line3" in result.stdout

    @pytest.mark.asyncio
    async def test_execute_path_expansion(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test ~ expansion in working directory."""
        node = ShellNode(
            type="shell",
            id="path-test",
            command="pwd",
            working_dir="~",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        # Should expand to home directory, not literal ~
        assert "~" not in result.stdout or os.path.expanduser("~") in result.stdout

    @pytest.mark.asyncio
    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-specific test")
    async def test_execute_pipe_command(
        self, executor: ShellExecutor, context: ExecutionContext
    ) -> None:
        """Test command with pipes."""
        node = ShellNode(
            type="shell",
            id="pipe-test",
            command="echo 'hello world' | tr 'a-z' 'A-Z'",
        )
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert "HELLO WORLD" in result.stdout

"""Tests for Claude CLI node executor."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flowpilot.engine import ExecutionContext
from flowpilot.engine.nodes import ClaudeCliExecutor
from flowpilot.engine.nodes.claude_cli import ClaudeCliNotFoundError
from flowpilot.models import ClaudeCliNode


@pytest.fixture
def executor() -> ClaudeCliExecutor:
    """Create a Claude CLI executor instance."""
    return ClaudeCliExecutor()


@pytest.fixture
def context() -> ExecutionContext:
    """Create an execution context."""
    return ExecutionContext(workflow_name="test-workflow", execution_id="test-exec-123")


class TestClaudeCliExecutor:
    """Tests for ClaudeCliExecutor."""

    @pytest.mark.asyncio
    async def test_execute_simple_prompt(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing a simple prompt."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="simple-prompt",
            prompt="Hello, Claude!",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Hello! How can I help you today?", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        assert "Hello! How can I help you today?" in result.output
        assert result.duration_ms >= 0
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_execute_with_model_selection(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with specific model."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="model-test",
            prompt="Test prompt",
            model="opus",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        # Verify --model opus was passed
        call_args = mock_exec.call_args
        assert "--model" in call_args[0]
        assert "opus" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_json_output(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with JSON output format."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="json-test",
            prompt="Return data as JSON",
            output_format="json",
        )

        json_response = json.dumps({"result": {"text": "Structured response"}})
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(json_response.encode(), b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "Structured response"
        assert "result" in result.data
        # Verify --output-format=json was passed
        call_args = mock_exec.call_args
        assert "--output-format=json" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_stream_json_output(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with stream-json output format."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="stream-json-test",
            prompt="Stream test",
            output_format="stream-json",
        )

        # Simulate streaming JSON output (newline-delimited)
        stream_response = (
            '{"type": "text", "text": "Hello "}\n'
            '{"type": "text", "text": "World!"}\n'
            '{"type": "done"}\n'
        )
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(stream_response.encode(), b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "Hello World!"
        assert "events" in result.data
        assert len(result.data["events"]) == 3

    @pytest.mark.asyncio
    async def test_execute_with_max_tokens(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with max tokens limit."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="max-tokens-test",
            prompt="Test",
            max_tokens=100,
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        call_args = mock_exec.call_args
        assert "--max-tokens" in call_args[0]
        assert "100" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_system_prompt(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with system prompt."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="system-prompt-test",
            prompt="Hello",
            system_prompt="You are a helpful assistant.",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        call_args = mock_exec.call_args
        assert "--system-prompt" in call_args[0]
        assert "You are a helpful assistant." in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_no_tools(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with tools disabled."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="no-tools-test",
            prompt="Test",
            no_tools=True,
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        call_args = mock_exec.call_args
        assert "--no-tools" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_allowed_tools(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test executing with restricted tool access."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="allowed-tools-test",
            prompt="Test",
            allowed_tools=["Read", "Write"],
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        call_args = mock_exec.call_args
        assert "--allowedTools" in call_args[0]
        assert "Read,Write" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_session_id(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test resuming a previous session."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="session-test",
            prompt="Continue our conversation",
            session_id="abc123-session",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Continued...", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        call_args = mock_exec.call_args
        assert "--resume" in call_args[0]
        assert "abc123-session" in call_args[0]

    @pytest.mark.asyncio
    async def test_execute_with_save_session(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test extracting session ID when saving."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="save-session-test",
            prompt="Start conversation",
            save_session=True,
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(
            return_value=(b"Response", b"Session ID: abc12345-def6-7890-ghij-klmnopqrstuv")
        )
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data.get("session_id") == "abc12345-def6-7890-ghij-klmnopqrstuv"

    @pytest.mark.asyncio
    async def test_execute_with_working_directory(
        self, executor: ClaudeCliExecutor, context: ExecutionContext, tmp_path: str
    ) -> None:
        """Test executing with working directory."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="working-dir-test",
            prompt="What files are here?",
            working_dir=str(tmp_path),
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Files: test.txt", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        # Verify cwd was passed
        call_kwargs = mock_exec.call_args.kwargs
        assert call_kwargs.get("cwd") is not None

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test command timeout handling."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="timeout-test",
            prompt="Long running task",
            timeout=1,
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(side_effect=TimeoutError())
        mock_proc.terminate = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock()

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await executor.execute(node, context)

        assert result.status == "error"
        assert "timed out" in result.error_message.lower()
        mock_proc.terminate.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_non_zero_exit(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test handling non-zero exit code."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="error-test",
            prompt="Failing prompt",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"Error occurred"))
        mock_proc.returncode = 1

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await executor.execute(node, context)

        assert result.status == "error"
        assert "exit" in result.error_message.lower()
        assert result.stderr == "Error occurred"

    @pytest.mark.asyncio
    async def test_execute_binary_not_found(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test error when Claude CLI is not found."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="not-found-test",
            prompt="Test",
        )

        with patch.object(
            executor,
            "_find_claude_binary",
            side_effect=ClaudeCliNotFoundError("Claude CLI not found"),
        ):
            result = await executor.execute(node, context)

        assert result.status == "error"
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_passes_environment(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test that FlowPilot environment variables are passed."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="env-test",
            prompt="Test",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Response", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec,
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        call_kwargs = mock_exec.call_args.kwargs
        env = call_kwargs.get("env", {})
        assert env.get("FLOWPILOT_EXECUTION_ID") == "test-exec-123"
        assert env.get("FLOWPILOT_WORKFLOW") == "test-workflow"

    @pytest.mark.asyncio
    async def test_execute_json_parse_error(
        self, executor: ClaudeCliExecutor, context: ExecutionContext
    ) -> None:
        """Test handling of invalid JSON output."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="json-error-test",
            prompt="Test",
            output_format="json",
        )

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"Not valid JSON", b""))
        mock_proc.returncode = 0

        with (
            patch.object(executor, "_find_claude_binary", return_value="/usr/bin/claude"),
            patch("asyncio.create_subprocess_exec", return_value=mock_proc),
        ):
            result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.output == "Not valid JSON"
        assert result.data.get("raw") == "Not valid JSON"


class TestClaudeCliFindBinary:
    """Tests for finding the Claude CLI binary."""

    def test_find_claude_binary_in_path(self) -> None:
        """Test finding claude binary using shutil.which."""
        # Create fresh executor to avoid cached path
        executor = ClaudeCliExecutor()
        with (
            patch(
                "flowpilot.engine.nodes.claude_cli.shutil.which",
                return_value="/usr/local/bin/claude",
            ),
            patch(
                "flowpilot.engine.nodes.claude_cli.Path.exists",
                return_value=True,
            ),
        ):
            path = executor._find_claude_binary()
            assert path == "/usr/local/bin/claude"

    def test_find_claude_binary_not_found(self) -> None:
        """Test error when claude binary is not found."""
        # Create fresh executor to avoid cached path
        executor = ClaudeCliExecutor()
        with (
            patch("flowpilot.engine.nodes.claude_cli.shutil.which", return_value=None),
            patch("flowpilot.engine.nodes.claude_cli.Path.exists", return_value=False),
            pytest.raises(ClaudeCliNotFoundError),
        ):
            executor._find_claude_binary()

    def test_find_claude_binary_caches_result(self, executor: ClaudeCliExecutor) -> None:
        """Test that found binary path is cached."""
        executor._claude_path = "/cached/path/claude"
        path = executor._find_claude_binary()
        assert path == "/cached/path/claude"


class TestClaudeCliOutputParsing:
    """Tests for output parsing methods."""

    def test_parse_output_text(self, executor: ClaudeCliExecutor) -> None:
        """Test parsing text output."""
        output, data = executor._parse_output("  Hello World  ", "text")
        assert output == "Hello World"
        assert data == {}

    def test_parse_output_json(self, executor: ClaudeCliExecutor) -> None:
        """Test parsing JSON output."""
        json_str = '{"result": {"text": "Response"}, "usage": {"tokens": 100}}'
        output, data = executor._parse_output(json_str, "json")
        assert output == "Response"
        assert data["result"]["text"] == "Response"
        assert data["usage"]["tokens"] == 100

    def test_parse_output_json_invalid(self, executor: ClaudeCliExecutor) -> None:
        """Test parsing invalid JSON output."""
        output, data = executor._parse_output("not json", "json")
        assert output == "not json"
        assert data["raw"] == "not json"

    def test_parse_output_stream_json(self, executor: ClaudeCliExecutor) -> None:
        """Test parsing streaming JSON output."""
        stream = '{"type": "text", "text": "Hello "}\n{"type": "text", "text": "World"}'
        output, data = executor._parse_output(stream, "stream-json")
        assert output == "Hello World"
        assert len(data["events"]) == 2

    def test_extract_session_id(self, executor: ClaudeCliExecutor) -> None:
        """Test extracting session ID from stderr."""
        stderr = "Some output\nSession ID: abc-123-def-456\nMore output"
        session_id = executor._extract_session_id(stderr)
        assert session_id == "abc-123-def-456"

    def test_extract_session_id_not_found(self, executor: ClaudeCliExecutor) -> None:
        """Test when session ID is not in stderr."""
        stderr = "No session info here"
        session_id = executor._extract_session_id(stderr)
        assert session_id is None


class TestClaudeCliNodeModel:
    """Tests for ClaudeCliNode model."""

    def test_minimal_node(self) -> None:
        """Test creating minimal claude-cli node."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="test",
            prompt="Hello",
        )
        assert node.type == "claude-cli"
        assert node.prompt == "Hello"
        assert node.model is None
        assert node.timeout == 300
        assert node.output_format == "text"

    def test_full_node(self) -> None:
        """Test creating claude-cli node with all options."""
        node = ClaudeCliNode(
            type="claude-cli",
            id="full-test",
            prompt="Complex prompt",
            model="opus",
            working_dir="/tmp",
            timeout=600,
            output_format="json",
            max_tokens=1000,
            system_prompt="Be helpful",
            allowed_tools=["Read", "Write"],
            no_tools=False,
            session_id="session-123",
            save_session=True,
        )
        assert node.model == "opus"
        assert node.working_dir == "/tmp"
        assert node.timeout == 600
        assert node.output_format == "json"
        assert node.max_tokens == 1000
        assert node.system_prompt == "Be helpful"
        assert node.allowed_tools == ["Read", "Write"]
        assert node.no_tools is False
        assert node.session_id == "session-123"
        assert node.save_session is True

    def test_invalid_model(self) -> None:
        """Test that invalid model raises error."""
        with pytest.raises(ValueError):
            ClaudeCliNode(
                type="claude-cli",
                id="test",
                prompt="Hello",
                model="invalid-model",  # type: ignore
            )

    def test_invalid_output_format(self) -> None:
        """Test that invalid output format raises error."""
        with pytest.raises(ValueError):
            ClaudeCliNode(
                type="claude-cli",
                id="test",
                prompt="Hello",
                output_format="invalid",  # type: ignore
            )

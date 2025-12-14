"""Tests for Claude API node executor."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import anthropic
import pytest

from flowpilot.config import ConfigError, get_anthropic_api_key
from flowpilot.engine.context import ExecutionContext
from flowpilot.engine.nodes.claude_api import (
    DEFAULT_PRICING,
    ClaudeApiExecutor,
)
from flowpilot.models import ClaudeApiNode

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def executor() -> ClaudeApiExecutor:
    """Create a fresh executor instance."""
    return ClaudeApiExecutor()


@pytest.fixture
def context() -> ExecutionContext:
    """Create a basic execution context."""
    return ExecutionContext(workflow_name="test-workflow")


@pytest.fixture
def basic_node() -> ClaudeApiNode:
    """Create a basic claude-api node."""
    return ClaudeApiNode(
        id="test-api",
        type="claude-api",
        prompt="Hello, Claude!",
    )


@pytest.fixture
def mock_response() -> MagicMock:
    """Create a mock API response."""
    response = MagicMock()
    response.content = [MagicMock(type="text", text="Hello! How can I help you?")]
    response.usage = MagicMock(input_tokens=10, output_tokens=20)
    response.stop_reason = "end_turn"
    return response


# ============================================================================
# Config Tests
# ============================================================================


class TestApiKeyConfig:
    """Tests for API key configuration."""

    def test_get_api_key_from_env(self) -> None:
        """Test getting API key from environment variable."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key-123"}):
            key = get_anthropic_api_key()
            assert key == "test-key-123"

    def test_get_api_key_missing_raises_error(self) -> None:
        """Test that missing API key raises ConfigError."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.exists", return_value=False),
        ):
            # Clear the environment variable if it exists
            import os

            env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                with pytest.raises(ConfigError, match="API key not found"):
                    get_anthropic_api_key()
            finally:
                if env_backup:
                    os.environ["ANTHROPIC_API_KEY"] = env_backup

    def test_get_api_key_from_flowpilot_config(self) -> None:
        """Test getting API key from FlowPilot config file."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.exists") as mock_exists,
            patch("builtins.open", MagicMock()),
            patch("yaml.safe_load", return_value={"anthropic": {"api_key": "config-key-456"}}),
        ):
            import os

            env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            mock_exists.return_value = True
            try:
                key = get_anthropic_api_key()
                assert key == "config-key-456"
            finally:
                if env_backup:
                    os.environ["ANTHROPIC_API_KEY"] = env_backup


# ============================================================================
# Executor Tests
# ============================================================================


class TestClaudeApiExecutor:
    """Tests for ClaudeApiExecutor."""

    @pytest.mark.asyncio
    async def test_successful_execution(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
        mock_response: MagicMock,
    ) -> None:
        """Test successful API execution."""
        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch.object(
                anthropic.AsyncAnthropic,
                "messages",
                new_callable=lambda: MagicMock(create=AsyncMock(return_value=mock_response)),
            ),
        ):
            result = await executor.execute(basic_node, context)

            assert result.status == "success"
            assert result.output == "Hello! How can I help you?"
            assert result.data["input_tokens"] == 10
            assert result.data["output_tokens"] == 20
            assert result.data["total_tokens"] == 30
            assert result.data["stop_reason"] == "end_turn"
            assert "cost_usd" in result.data

    @pytest.mark.asyncio
    async def test_execution_with_system_prompt(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        mock_response: MagicMock,
    ) -> None:
        """Test execution with system prompt."""
        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Hello!",
            system="You are a helpful assistant.",
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"
            # Verify system prompt was passed
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["system"] == "You are a helpful assistant."

    @pytest.mark.asyncio
    async def test_execution_with_temperature(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        mock_response: MagicMock,
    ) -> None:
        """Test execution with temperature parameter."""
        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Hello!",
            temperature=0.7,
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_execution_with_all_generation_params(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        mock_response: MagicMock,
    ) -> None:
        """Test execution with all generation parameters."""
        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Hello!",
            temperature=0.5,
            top_p=0.9,
            top_k=50,
            max_tokens=1000,
            stop_sequences=["END", "STOP"],
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.5
            assert call_kwargs["top_p"] == 0.9
            assert call_kwargs["top_k"] == 50
            assert call_kwargs["max_tokens"] == 1000
            assert call_kwargs["stop_sequences"] == ["END", "STOP"]

    @pytest.mark.asyncio
    async def test_json_output_format(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
    ) -> None:
        """Test JSON output format parsing."""
        json_response = {"name": "Claude", "type": "AI"}
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text=json.dumps(json_response))]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_response.stop_reason = "end_turn"

        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Return JSON",
            output_format="json",
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"
            assert result.data["parsed"] == json_response
            # Verify JSON instruction was added to system
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert "valid JSON" in call_kwargs.get("system", "")

    @pytest.mark.asyncio
    async def test_json_output_with_schema(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
    ) -> None:
        """Test JSON output with schema hint."""
        schema = {"type": "object", "properties": {"name": {"type": "string"}}}
        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Return JSON",
            output_format="json",
            json_schema=schema,
        )

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text='{"name": "test"}')]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"
            call_kwargs = mock_client.messages.create.call_args.kwargs
            # Verify schema was included in system prompt
            assert "schema" in call_kwargs.get("system", "").lower()

    @pytest.mark.asyncio
    async def test_json_parse_error(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
    ) -> None:
        """Test JSON parse error handling."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="not valid json")]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_response.stop_reason = "end_turn"

        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Return JSON",
            output_format="json",
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"  # Still success, just with parse error
            assert "parse_error" in result.data["parsed"]
            assert result.data["parsed"]["raw"] == "not valid json"

    @pytest.mark.asyncio
    async def test_custom_messages(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        mock_response: MagicMock,
    ) -> None:
        """Test execution with custom message history."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]
        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="This is ignored",
            messages=messages,
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "success"
            call_kwargs = mock_client.messages.create.call_args.kwargs
            assert call_kwargs["messages"] == messages

    @pytest.mark.asyncio
    async def test_missing_api_key(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
    ) -> None:
        """Test error when API key is missing."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("pathlib.Path.exists", return_value=False),
        ):
            import os

            env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                result = await executor.execute(basic_node, context)

                assert result.status == "error"
                assert "API key not found" in str(result.error_message)
            finally:
                if env_backup:
                    os.environ["ANTHROPIC_API_KEY"] = env_backup

    @pytest.mark.asyncio
    async def test_connection_error(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
    ) -> None:
        """Test API connection error handling."""
        mock_client = MagicMock()
        mock_client.messages = MagicMock(
            create=AsyncMock(side_effect=anthropic.APIConnectionError(request=MagicMock()))
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(basic_node, context)

            assert result.status == "error"
            assert "connection error" in str(result.error_message).lower()

    @pytest.mark.asyncio
    async def test_rate_limit_error(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
    ) -> None:
        """Test rate limit error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.messages = MagicMock(
            create=AsyncMock(
                side_effect=anthropic.RateLimitError(
                    message="Rate limit exceeded",
                    response=mock_response,
                    body=None,
                )
            )
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(basic_node, context)

            assert result.status == "error"
            assert "rate limit" in str(result.error_message).lower()
            assert "retry_after" in result.data

    @pytest.mark.asyncio
    async def test_api_status_error(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
    ) -> None:
        """Test API status error handling."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.headers = {}

        mock_client = MagicMock()
        mock_client.messages = MagicMock(
            create=AsyncMock(
                side_effect=anthropic.APIStatusError(
                    message="Internal server error",
                    response=mock_response,
                    body=None,
                )
            )
        )

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(basic_node, context)

            assert result.status == "error"
            assert "500" in str(result.error_message)

    @pytest.mark.asyncio
    async def test_timeout_error(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
    ) -> None:
        """Test timeout error handling."""
        node = ClaudeApiNode(
            id="test-api",
            type="claude-api",
            prompt="Hello!",
            timeout=1,  # Very short timeout
        )

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(side_effect=TimeoutError()))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(node, context)

            assert result.status == "error"
            assert "timed out" in str(result.error_message).lower()


# ============================================================================
# Cost Calculation Tests
# ============================================================================


class TestCostCalculation:
    """Tests for cost calculation."""

    def test_calculate_cost_known_model(self, executor: ClaudeApiExecutor) -> None:
        """Test cost calculation for a known model."""
        cost = executor._calculate_cost(
            "claude-3-sonnet-20240229",
            input_tokens=1000,
            output_tokens=500,
        )
        # Input: 1000 / 1M * 3.00 = 0.003
        # Output: 500 / 1M * 15.00 = 0.0075
        # Total: 0.0105
        assert cost == pytest.approx(0.0105, rel=0.01)

    def test_calculate_cost_opus(self, executor: ClaudeApiExecutor) -> None:
        """Test cost calculation for Opus model."""
        cost = executor._calculate_cost(
            "claude-3-opus-20240229",
            input_tokens=1000,
            output_tokens=500,
        )
        # Input: 1000 / 1M * 15.00 = 0.015
        # Output: 500 / 1M * 75.00 = 0.0375
        # Total: 0.0525
        assert cost == pytest.approx(0.0525, rel=0.01)

    def test_calculate_cost_haiku(self, executor: ClaudeApiExecutor) -> None:
        """Test cost calculation for Haiku model."""
        cost = executor._calculate_cost(
            "claude-3-haiku-20240307",
            input_tokens=1000,
            output_tokens=500,
        )
        # Input: 1000 / 1M * 0.25 = 0.00025
        # Output: 500 / 1M * 1.25 = 0.000625
        # Total: 0.000875
        assert cost == pytest.approx(0.000875, rel=0.01)

    def test_calculate_cost_unknown_model(self, executor: ClaudeApiExecutor) -> None:
        """Test cost calculation falls back to default for unknown model."""
        cost = executor._calculate_cost(
            "claude-unknown-model",
            input_tokens=1000,
            output_tokens=500,
        )
        # Uses default pricing (same as sonnet)
        expected = (1000 / 1_000_000 * DEFAULT_PRICING["input"]) + (
            500 / 1_000_000 * DEFAULT_PRICING["output"]
        )
        assert cost == pytest.approx(expected, rel=0.01)

    def test_calculate_cost_zero_tokens(self, executor: ClaudeApiExecutor) -> None:
        """Test cost calculation with zero tokens."""
        cost = executor._calculate_cost(
            "claude-3-sonnet-20240229",
            input_tokens=0,
            output_tokens=0,
        )
        assert cost == 0.0


# ============================================================================
# Node Model Tests
# ============================================================================


class TestClaudeApiNodeModel:
    """Tests for ClaudeApiNode model validation."""

    def test_minimal_node(self) -> None:
        """Test creating node with minimal required fields."""
        node = ClaudeApiNode(
            id="test",
            type="claude-api",
            prompt="Hello",
        )
        assert node.prompt == "Hello"
        assert node.model == "claude-sonnet-4-20250514"
        assert node.max_tokens == 4096
        assert node.temperature is None

    def test_full_node(self) -> None:
        """Test creating node with all fields."""
        node = ClaudeApiNode(
            id="test",
            type="claude-api",
            prompt="Hello",
            model="claude-3-opus-20240229",
            system="You are helpful.",
            max_tokens=2000,
            temperature=0.7,
            top_p=0.9,
            top_k=40,
            stop_sequences=["END"],
            output_format="json",
            json_schema={"type": "object"},
            timeout=60,
            metadata={"user_id": "test-user"},
            messages=[{"role": "user", "content": "Hi"}],
        )
        assert node.model == "claude-3-opus-20240229"
        assert node.temperature == 0.7
        assert node.top_p == 0.9
        assert node.top_k == 40
        assert node.output_format == "json"

    def test_temperature_validation(self) -> None:
        """Test temperature validation bounds."""
        # Valid temperature
        node = ClaudeApiNode(
            id="test",
            type="claude-api",
            prompt="Hello",
            temperature=0.5,
        )
        assert node.temperature == 0.5

        # Invalid temperature (too high)
        with pytest.raises(ValueError):
            ClaudeApiNode(
                id="test",
                type="claude-api",
                prompt="Hello",
                temperature=1.5,
            )

        # Invalid temperature (negative)
        with pytest.raises(ValueError):
            ClaudeApiNode(
                id="test",
                type="claude-api",
                prompt="Hello",
                temperature=-0.1,
            )

    def test_max_tokens_validation(self) -> None:
        """Test max_tokens validation."""
        # Valid max_tokens
        node = ClaudeApiNode(
            id="test",
            type="claude-api",
            prompt="Hello",
            max_tokens=100,
        )
        assert node.max_tokens == 100

        # Invalid max_tokens (zero)
        with pytest.raises(ValueError):
            ClaudeApiNode(
                id="test",
                type="claude-api",
                prompt="Hello",
                max_tokens=0,
            )

    def test_timeout_validation(self) -> None:
        """Test timeout validation."""
        # Valid timeout
        node = ClaudeApiNode(
            id="test",
            type="claude-api",
            prompt="Hello",
            timeout=300,
        )
        assert node.timeout == 300

        # Invalid timeout (zero)
        with pytest.raises(ValueError):
            ClaudeApiNode(
                id="test",
                type="claude-api",
                prompt="Hello",
                timeout=0,
            )


# ============================================================================
# Integration Tests
# ============================================================================


class TestClaudeApiIntegration:
    """Integration tests for Claude API executor."""

    @pytest.mark.asyncio
    async def test_executor_registered(self) -> None:
        """Test that executor is registered in the registry."""
        import importlib

        import flowpilot.engine.nodes.claude_api as claude_api_module
        from flowpilot.engine.executor import ExecutorRegistry

        # Reload module to re-trigger registration (in case registry was cleared)
        importlib.reload(claude_api_module)

        assert ExecutorRegistry.has_executor("claude-api")
        executor = ExecutorRegistry.get("claude-api")
        # Check by class name since reload creates new class identity
        assert executor.__class__.__name__ == "ClaudeApiExecutor"

    @pytest.mark.asyncio
    async def test_multiple_content_blocks(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
    ) -> None:
        """Test handling response with multiple content blocks."""
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(type="text", text="Part 1"),
            MagicMock(type="text", text=" Part 2"),
            MagicMock(type="text", text=" Part 3"),
        ]
        mock_response.usage = MagicMock(input_tokens=10, output_tokens=20)
        mock_response.stop_reason = "end_turn"

        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(basic_node, context)

            assert result.status == "success"
            assert result.output == "Part 1 Part 2 Part 3"

    @pytest.mark.asyncio
    async def test_result_metadata(
        self,
        executor: ClaudeApiExecutor,
        context: ExecutionContext,
        basic_node: ClaudeApiNode,
        mock_response: MagicMock,
    ) -> None:
        """Test that result contains all expected metadata."""
        mock_client = MagicMock()
        mock_client.messages = MagicMock(create=AsyncMock(return_value=mock_response))

        with (
            patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}),
            patch("anthropic.AsyncAnthropic", return_value=mock_client),
        ):
            result = await executor.execute(basic_node, context)

            assert result.status == "success"
            assert result.started_at is not None
            assert result.finished_at is not None
            assert result.duration_ms >= 0
            assert "model" in result.data
            assert "input_tokens" in result.data
            assert "output_tokens" in result.data
            assert "total_tokens" in result.data
            assert "cost_usd" in result.data
            assert "stop_reason" in result.data

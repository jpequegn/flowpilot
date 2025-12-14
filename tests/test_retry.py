"""Tests for retry executor."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from flowpilot.engine.context import ExecutionContext, NodeResult
from flowpilot.engine.errors import ErrorCategory, FlowPilotError
from flowpilot.engine.retry import RetryExecutor, calculate_backoff
from flowpilot.models import RetryConfig


class TestCalculateBackoff:
    """Tests for calculate_backoff function."""

    def test_first_attempt(self) -> None:
        """Test backoff for first attempt (0-indexed)."""
        backoff = calculate_backoff(
            attempt=0,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert backoff == 1.0

    def test_second_attempt(self) -> None:
        """Test backoff for second attempt."""
        backoff = calculate_backoff(
            attempt=1,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert backoff == 2.0

    def test_third_attempt(self) -> None:
        """Test backoff for third attempt."""
        backoff = calculate_backoff(
            attempt=2,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert backoff == 4.0

    def test_max_delay_cap(self) -> None:
        """Test backoff is capped at max_delay."""
        backoff = calculate_backoff(
            attempt=10,
            initial_delay=10.0,
            max_delay=30.0,
            exponential_base=2.0,
            jitter=False,
        )
        assert backoff == 30.0

    def test_jitter_adds_randomness(self) -> None:
        """Test jitter adds randomness to backoff."""
        # Run multiple times and check we get different values
        backoffs = [
            calculate_backoff(
                attempt=1,
                initial_delay=1.0,
                max_delay=60.0,
                exponential_base=2.0,
                jitter=True,
            )
            for _ in range(10)
        ]
        # With jitter, values should vary between 1.0 and 3.0 (2.0 * (0.5 + 0-1))
        assert all(1.0 <= b <= 3.0 for b in backoffs)
        # Very unlikely all values are identical with jitter
        assert len(set(backoffs)) > 1

    def test_retry_after_override(self) -> None:
        """Test retry_after overrides calculated delay."""
        backoff = calculate_backoff(
            attempt=0,
            initial_delay=1.0,
            max_delay=60.0,
            exponential_base=2.0,
            jitter=True,
            retry_after=30,
        )
        assert backoff == 30.0


class TestRetryExecutor:
    """Tests for RetryExecutor class."""

    @pytest.fixture
    def context(self) -> ExecutionContext:
        """Create test execution context."""
        return ExecutionContext(
            workflow_name="test-workflow",
            execution_id="test-123",
            inputs={},
            started_at=datetime.now(),
        )

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock node executor."""
        executor = MagicMock()
        executor.execute = AsyncMock()
        return executor

    @pytest.fixture
    def mock_node(self) -> MagicMock:
        """Create mock node."""
        node = MagicMock()
        node.id = "test-node"
        node.type = "claude"
        node.retry = RetryConfig(max_attempts=3, initial_delay=0.1, jitter=False)
        node.timeout = 30
        return node

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test successful execution on first attempt."""
        mock_executor.execute.return_value = NodeResult.success(output="test output")

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "success"
        assert result.output == "test output"
        assert mock_executor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_success_after_exception_retry(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test success after transient exception."""
        # First call raises exception, second succeeds
        mock_executor.execute.side_effect = [
            Exception("Connection timeout"),
            NodeResult.success(output="test output"),
        ]

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "success"
        assert result.output == "test output"
        assert mock_executor.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test failure after max retries exceeded."""
        # All attempts fail with exception
        mock_executor.execute.side_effect = Exception("Connection timeout")

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "error"
        assert mock_executor.execute.call_count == 3  # max_attempts

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test permanent errors are not retried."""
        # Raise a permanent error (auth)
        mock_executor.execute.side_effect = FlowPilotError(
            message="Authentication failed",
            category=ErrorCategory.PERMANENT,
            retryable=False,
        )

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "error"
        # Should only try once for permanent errors
        assert mock_executor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_transient_error_retried(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test transient errors are retried."""
        mock_executor.execute.side_effect = [
            FlowPilotError(
                message="Connection timeout",
                category=ErrorCategory.TRANSIENT,
                retryable=True,
            ),
            NodeResult.success(output="recovered"),
        ]

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "success"
        assert result.output == "recovered"
        assert mock_executor.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_resource_error_retried(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test resource errors are retried."""
        mock_executor.execute.side_effect = [
            FlowPilotError(
                message="Rate limited",
                category=ErrorCategory.RESOURCE,
                retryable=True,
            ),
            NodeResult.success(output="recovered"),
        ]

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "success"
        assert result.output == "recovered"
        assert mock_executor.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_disabled_for_transient(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test retry can be disabled for transient errors."""
        mock_node.retry = RetryConfig(max_attempts=3, retry_on_transient=False, initial_delay=0.1)
        mock_executor.execute.side_effect = FlowPilotError(
            message="Connection timeout",
            category=ErrorCategory.TRANSIENT,
            retryable=True,
        )

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "error"
        assert mock_executor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_disabled_for_resource(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test retry can be disabled for resource errors."""
        mock_node.retry = RetryConfig(max_attempts=3, retry_on_resource=False, initial_delay=0.1)
        mock_executor.execute.side_effect = FlowPilotError(
            message="Rate limited",
            category=ErrorCategory.RESOURCE,
            retryable=True,
        )

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "error"
        assert mock_executor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_uses_default_config(
        self, context: ExecutionContext, mock_executor: MagicMock
    ) -> None:
        """Test uses default config when node has no retry config."""
        node = MagicMock()
        node.id = "test-node"
        node.type = "claude"
        node.retry = None  # No config on node
        node.timeout = 30

        mock_executor.execute.return_value = NodeResult.success(output="test output")

        default_config = RetryConfig(max_attempts=5, initial_delay=0.5)
        retry_executor = RetryExecutor(default_config=default_config)
        result = await retry_executor.execute_with_retry(mock_executor, node, context)

        assert result.status == "success"

    @pytest.mark.asyncio
    async def test_exception_during_execution(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test handling of exceptions during execution."""
        mock_executor.execute.side_effect = Exception("Unexpected error")

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        # Should try all attempts and return error
        assert result.status == "error"
        assert "Unexpected error" in result.error_message

    @pytest.mark.asyncio
    async def test_error_result_triggers_retry_for_retryable_message(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test that error result with retryable message triggers retry."""
        # Return error result with retryable message
        mock_executor.execute.side_effect = [
            NodeResult.error("Connection timeout"),  # Retryable message
            NodeResult.success(output="recovered"),
        ]

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "success"
        assert mock_executor.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_error_result_no_retry_for_permanent_message(
        self, context: ExecutionContext, mock_executor: MagicMock, mock_node: MagicMock
    ) -> None:
        """Test that error result with permanent error message doesn't retry."""
        # Return error result with permanent message
        mock_executor.execute.return_value = NodeResult.error("Authentication failed")

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(mock_executor, mock_node, context)

        assert result.status == "error"
        # Should only try once for permanent errors
        assert mock_executor.execute.call_count == 1


class TestRetryExecutorIntegration:
    """Integration tests for RetryExecutor."""

    @pytest.fixture
    def context(self) -> ExecutionContext:
        """Create test execution context."""
        return ExecutionContext(
            workflow_name="test-workflow",
            execution_id="test-123",
            inputs={},
            started_at=datetime.now(),
        )

    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, context: ExecutionContext) -> None:
        """Test that backoff timing is approximately correct."""
        execution_times: list[float] = []
        call_count = 0

        async def mock_execute(*args: Any, **kwargs: Any) -> NodeResult:
            nonlocal call_count
            call_count += 1
            execution_times.append(asyncio.get_event_loop().time())
            # First two calls fail, third succeeds
            if call_count < 3:
                raise FlowPilotError(
                    message="Transient error",
                    category=ErrorCategory.TRANSIENT,
                    retryable=True,
                )
            return NodeResult.success(output="done")

        executor = MagicMock()
        executor.execute = mock_execute

        node = MagicMock()
        node.id = "test-node"
        node.type = "claude"
        node.retry = RetryConfig(
            max_attempts=5,  # Allow enough attempts
            initial_delay=0.1,
            exponential_base=2.0,
            jitter=False,
        )
        node.timeout = 30

        retry_executor = RetryExecutor()
        result = await retry_executor.execute_with_retry(executor, node, context)

        assert result.status == "success"
        assert len(execution_times) == 3

        # Check timing gaps (with some tolerance for execution overhead)
        first_gap = execution_times[1] - execution_times[0]
        second_gap = execution_times[2] - execution_times[1]

        # First delay should be ~0.1s, second ~0.2s
        assert 0.05 <= first_gap <= 0.3  # Allow for some variance
        assert 0.1 <= second_gap <= 0.5

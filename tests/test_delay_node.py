"""Tests for delay node executor."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from flowpilot.engine.context import ExecutionContext
from flowpilot.engine.executor import ExecutorRegistry
from flowpilot.engine.nodes.delay import DelayExecutor
from flowpilot.models import DelayNode


class TestDelayNodeModel:
    """Tests for DelayNode model."""

    def test_create_delay_node_with_duration(self) -> None:
        """Test creating a delay node with duration."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="5s",
        )
        assert node.id == "test-delay"
        assert node.type == "delay"
        assert node.duration == "5s"
        assert node.until is None

    def test_create_delay_node_with_until(self) -> None:
        """Test creating a delay node with until."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            until="2024-12-15T10:30:00",
        )
        assert node.until == "2024-12-15T10:30:00"
        assert node.duration is None

    def test_create_delay_node_with_both(self) -> None:
        """Test creating a delay node with both duration and until."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="5s",
            until="2024-12-15T10:30:00",
        )
        assert node.duration == "5s"
        assert node.until == "2024-12-15T10:30:00"


class TestDelayExecutor:
    """Tests for DelayExecutor class."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure DelayExecutor is registered."""
        if not ExecutorRegistry.has_executor("delay"):
            ExecutorRegistry.register("delay")(DelayExecutor)

    def test_executor_registered(self) -> None:
        """Test DelayExecutor is registered."""
        if not ExecutorRegistry.has_executor("delay"):
            ExecutorRegistry.register("delay")(DelayExecutor)
        assert ExecutorRegistry.has_executor("delay")
        executor = ExecutorRegistry.get("delay")
        assert isinstance(executor, DelayExecutor)

    @pytest.mark.asyncio
    async def test_delay_duration_seconds(self) -> None:
        """Test delay with seconds duration."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="0.1s",
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        start = datetime.now(UTC)
        result = await executor.execute(node, context)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        assert result.status == "success"
        assert result.data["wait_type"] == "duration"
        assert result.data["requested_seconds"] == pytest.approx(0.1, abs=0.01)
        assert elapsed >= 0.1

    @pytest.mark.asyncio
    async def test_delay_duration_minutes(self) -> None:
        """Test delay with minutes duration (short test)."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="0.01m",  # 0.6 seconds
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["wait_type"] == "duration"
        assert result.data["requested_seconds"] == pytest.approx(0.6, abs=0.01)

    @pytest.mark.asyncio
    async def test_delay_no_duration_or_until(self) -> None:
        """Test delay with neither duration nor until."""
        node = DelayNode(
            id="test-delay",
            type="delay",
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert "Either 'duration' or 'until' must be specified" in result.error_message

    @pytest.mark.asyncio
    async def test_delay_invalid_duration_format(self) -> None:
        """Test delay with invalid duration format."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="invalid",
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        result = await executor.execute(node, context)

        assert result.status == "error"
        assert "Invalid duration format" in result.error_message

    @pytest.mark.asyncio
    async def test_delay_until_past_time(self) -> None:
        """Test delay with until time in the past."""
        past_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        node = DelayNode(
            id="test-delay",
            type="delay",
            until=past_time,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["skipped"] is True
        assert "already passed" in result.output

    @pytest.mark.asyncio
    async def test_delay_until_future_time(self) -> None:
        """Test delay with until time in the future."""
        # Set target time 0.1 seconds from now
        future_time = (datetime.now(UTC) + timedelta(seconds=0.1)).isoformat()
        node = DelayNode(
            id="test-delay",
            type="delay",
            until=future_time,
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        start = datetime.now(UTC)
        result = await executor.execute(node, context)
        elapsed = (datetime.now(UTC) - start).total_seconds()

        assert result.status == "success"
        assert result.data["wait_type"] == "until"
        assert elapsed >= 0.09  # Allow small margin


class TestDelayDurationParsing:
    """Tests for duration string parsing."""

    @pytest.fixture
    def executor(self) -> DelayExecutor:
        """Create executor instance."""
        return DelayExecutor()

    def test_parse_seconds(self, executor: DelayExecutor) -> None:
        """Test parsing seconds."""
        assert executor._parse_duration("30s") == 30
        assert executor._parse_duration("30 sec") == 30
        assert executor._parse_duration("30 seconds") == 30
        assert executor._parse_duration("1second") == 1

    def test_parse_minutes(self, executor: DelayExecutor) -> None:
        """Test parsing minutes."""
        assert executor._parse_duration("5m") == 300
        assert executor._parse_duration("5 min") == 300
        assert executor._parse_duration("5 minutes") == 300
        assert executor._parse_duration("1minute") == 60

    def test_parse_hours(self, executor: DelayExecutor) -> None:
        """Test parsing hours."""
        assert executor._parse_duration("2h") == 7200
        assert executor._parse_duration("2 hr") == 7200
        assert executor._parse_duration("2 hours") == 7200
        assert executor._parse_duration("1hour") == 3600

    def test_parse_days(self, executor: DelayExecutor) -> None:
        """Test parsing days."""
        assert executor._parse_duration("1d") == 86400
        assert executor._parse_duration("1 day") == 86400
        assert executor._parse_duration("2 days") == 172800

    def test_parse_fractional(self, executor: DelayExecutor) -> None:
        """Test parsing fractional values."""
        assert executor._parse_duration("1.5s") == 1.5
        assert executor._parse_duration("0.5m") == 30
        assert executor._parse_duration("0.25h") == 900

    def test_parse_case_insensitive(self, executor: DelayExecutor) -> None:
        """Test case insensitivity."""
        assert executor._parse_duration("30S") == 30
        assert executor._parse_duration("5M") == 300
        assert executor._parse_duration("2H") == 7200
        assert executor._parse_duration("1D") == 86400

    def test_parse_invalid_format(self, executor: DelayExecutor) -> None:
        """Test invalid duration formats."""
        with pytest.raises(ValueError, match="Invalid duration format"):
            executor._parse_duration("invalid")

        with pytest.raises(ValueError, match="Invalid duration format"):
            executor._parse_duration("30")  # Missing unit

        with pytest.raises(ValueError, match="Invalid duration format"):
            executor._parse_duration("seconds")  # Missing value

        with pytest.raises(ValueError, match="Invalid duration format"):
            executor._parse_duration("30x")  # Invalid unit


class TestDelayUntilParsing:
    """Tests for until time parsing."""

    @pytest.fixture
    def executor(self) -> DelayExecutor:
        """Create executor instance."""
        return DelayExecutor()

    @pytest.fixture
    def context(self) -> ExecutionContext:
        """Create execution context."""
        return ExecutionContext(workflow_name="test", inputs={})

    def test_parse_iso_datetime(self, executor: DelayExecutor, context: ExecutionContext) -> None:
        """Test parsing ISO datetime."""
        future = datetime.now(UTC) + timedelta(hours=1)
        seconds = executor._parse_until(future.isoformat(), context)
        assert seconds > 0
        assert seconds <= 3600 + 1  # Allow 1 second margin

    def test_parse_iso_datetime_with_z(
        self, executor: DelayExecutor, context: ExecutionContext
    ) -> None:
        """Test parsing ISO datetime with Z suffix."""
        future = datetime.now(UTC) + timedelta(hours=1)
        iso_str = future.strftime("%Y-%m-%dT%H:%M:%SZ")
        seconds = executor._parse_until(iso_str, context)
        assert seconds > 0

    def test_parse_time_only_future(
        self, executor: DelayExecutor, context: ExecutionContext
    ) -> None:
        """Test parsing time-only format (future time today)."""
        # Get a time 1 minute from now
        future = datetime.now(UTC) + timedelta(minutes=1)
        time_str = future.strftime("%H:%M")

        seconds = executor._parse_until(time_str, context)
        assert seconds > 0
        assert seconds <= 60 + 1  # Allow 1 second margin

    def test_parse_time_only_past_rolls_to_tomorrow(
        self, executor: DelayExecutor, context: ExecutionContext
    ) -> None:
        """Test that past time-only format rolls to tomorrow."""
        # Get a time 1 minute ago
        past = datetime.now(UTC) - timedelta(minutes=1)
        time_str = past.strftime("%H:%M")

        seconds = executor._parse_until(time_str, context)
        # Should be close to 24 hours minus 1 minute
        assert seconds > 86400 - 120  # 24 hours minus 2 minutes
        assert seconds < 86400 + 60  # 24 hours plus 1 minute

    def test_parse_invalid_format(self, executor: DelayExecutor, context: ExecutionContext) -> None:
        """Test invalid until formats."""
        with pytest.raises(ValueError, match="Cannot parse 'until' value"):
            executor._parse_until("invalid", context)

        with pytest.raises(ValueError, match="Cannot parse 'until' value"):
            executor._parse_until("tomorrow", context)


class TestDelayCancellation:
    """Tests for delay cancellation behavior."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure DelayExecutor is registered."""
        if not ExecutorRegistry.has_executor("delay"):
            ExecutorRegistry.register("delay")(DelayExecutor)

    @pytest.mark.asyncio
    async def test_delay_cancellation(self) -> None:
        """Test that delay can be cancelled."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="10s",  # Long delay
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()

        # Start the delay and cancel it
        task = asyncio.create_task(executor.execute(node, context))

        # Give it a moment to start
        await asyncio.sleep(0.05)

        # Cancel the task
        task.cancel()

        try:
            result = await task
        except asyncio.CancelledError:
            # The task was cancelled before returning
            pass
        else:
            # The executor caught the cancellation
            assert result.status == "skipped"
            assert result.data["cancelled"] is True
            assert result.data["actual_seconds"] < 1


class TestDelayIntegration:
    """Integration tests for delay execution."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Ensure DelayExecutor is registered."""
        if not ExecutorRegistry.has_executor("delay"):
            ExecutorRegistry.register("delay")(DelayExecutor)

    @pytest.mark.asyncio
    async def test_delay_result_format(self) -> None:
        """Test delay result format."""
        node = DelayNode(
            id="test-delay",
            type="delay",
            duration="0.05s",
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={},
        )

        executor = DelayExecutor()
        result = await executor.execute(node, context)

        # Check result structure
        assert result.status == "success"
        assert "Waited" in result.output
        assert "requested_seconds" in result.data
        assert "actual_seconds" in result.data
        assert "wait_type" in result.data
        assert result.duration_ms >= 0
        assert result.started_at is not None
        assert result.finished_at is not None

    @pytest.mark.asyncio
    async def test_delay_with_template_until(self) -> None:
        """Test delay with template expression in until."""
        # Calculate a future time
        future = datetime.now(UTC) + timedelta(seconds=0.1)
        future_iso = future.isoformat()

        node = DelayNode(
            id="test-delay",
            type="delay",
            until="{{ inputs.target_time }}",
        )
        context = ExecutionContext(
            workflow_name="test",
            inputs={"target_time": future_iso},
        )

        executor = DelayExecutor()
        result = await executor.execute(node, context)

        assert result.status == "success"
        assert result.data["wait_type"] == "until"

    @pytest.mark.asyncio
    async def test_multiple_duration_formats(self) -> None:
        """Test various duration format variations."""
        executor = DelayExecutor()
        context = ExecutionContext(workflow_name="test", inputs={})

        formats = [
            ("0.05s", 0.05),
            ("0.05 s", 0.05),
            ("0.05sec", 0.05),
            ("0.05 sec", 0.05),
        ]

        for duration, expected in formats:
            node = DelayNode(id="test", type="delay", duration=duration)
            result = await executor.execute(node, context)
            assert result.status == "success", f"Failed for duration: {duration}"
            assert result.data["requested_seconds"] == pytest.approx(expected, abs=0.01)

"""Tests for circuit breaker pattern."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from flowpilot.engine.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    clear_all_circuit_breakers,
    get_all_circuit_breakers,
    get_circuit_breaker,
    reset_circuit_breaker,
)
from flowpilot.engine.errors import CircuitOpenError


class CircuitBreakerTestError(Exception):
    """Custom exception for circuit breaker tests."""

    pass


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_states_exist(self) -> None:
        """Test all circuit states are defined."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Clear circuit breakers before each test."""
        clear_all_circuit_breakers()

    def test_create_circuit_breaker(self) -> None:
        """Test creating a circuit breaker."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=3,
            recovery_timeout=30,
        )
        assert breaker.name == "test"
        assert breaker.failure_threshold == 3
        assert breaker.recovery_timeout == 30
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_successful_call(self) -> None:
        """Test successful call through circuit breaker."""
        breaker = CircuitBreaker(name="test")

        async def success_func() -> str:
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 1

    @pytest.mark.asyncio
    async def test_failed_call_increments_failure_count(self) -> None:
        """Test failed call increments failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        with pytest.raises(CircuitBreakerTestError):
            await breaker.call(fail_func)

        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self) -> None:
        """Test circuit opens after failure threshold."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        # Trigger failures up to threshold
        for _ in range(3):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN
        assert breaker.failure_count == 3

    @pytest.mark.asyncio
    async def test_open_circuit_rejects_calls(self) -> None:
        """Test open circuit rejects calls immediately."""
        breaker = CircuitBreaker(name="test", failure_threshold=3, recovery_timeout=60)

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        # Open the circuit
        for _ in range(3):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        # Now calls should be rejected
        with pytest.raises(CircuitOpenError) as exc_info:
            await breaker.call(fail_func)

        assert "open" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self) -> None:
        """Test circuit transitions to half-open after timeout."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1,  # 1 second timeout
        )

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        async def success_func() -> str:
            return "recovered"

        # Next call should transition to half-open and succeed
        result = await breaker.call(success_func)
        assert result == "recovered"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self) -> None:
        """Test half-open state failure reopens circuit."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1,
        )

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # Fail again in half-open state
        with pytest.raises(CircuitBreakerTestError):
            await breaker.call(fail_func)

        # Should be back to open
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_half_open_max_requests(self) -> None:
        """Test half-open state limits test requests."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=1,
            half_open_requests=1,
        )

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        async def slow_func() -> str:
            await asyncio.sleep(0.5)
            return "slow"

        # Start first half-open request (will succeed but take time)
        # We need to manually set state for this test
        breaker.state = CircuitState.HALF_OPEN
        breaker.half_open_count = 1

        # Second request should be rejected
        with pytest.raises(CircuitOpenError):
            await breaker.call(slow_func)

    def test_reset_circuit_breaker(self) -> None:
        """Test resetting circuit breaker."""
        breaker = CircuitBreaker(name="test", failure_threshold=2)
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 5
        breaker.success_count = 10
        breaker.last_failure_time = datetime.now(UTC)

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.last_failure_time is None

    def test_get_stats(self) -> None:
        """Test getting circuit breaker stats."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=5,
            recovery_timeout=60,
        )
        breaker.failure_count = 3
        breaker.success_count = 10

        stats = breaker.get_stats()

        assert stats["name"] == "test"
        assert stats["state"] == "closed"
        assert stats["failure_count"] == 3
        assert stats["success_count"] == 10
        assert stats["failure_threshold"] == 5
        assert stats["recovery_timeout"] == 60

    @pytest.mark.asyncio
    async def test_concurrent_calls(self) -> None:
        """Test circuit breaker handles concurrent calls."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)
        call_count = 0

        async def tracked_func() -> str:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)
            return "success"

        # Make concurrent calls
        results = await asyncio.gather(*[breaker.call(tracked_func) for _ in range(10)])

        assert all(r == "success" for r in results)
        assert call_count == 10
        assert breaker.success_count == 10


class TestGlobalCircuitBreakers:
    """Tests for global circuit breaker management."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Clear circuit breakers before each test."""
        clear_all_circuit_breakers()

    def test_get_circuit_breaker_creates_new(self) -> None:
        """Test get_circuit_breaker creates new breaker."""
        breaker = get_circuit_breaker("api-client")
        assert breaker.name == "api-client"
        assert breaker.state == CircuitState.CLOSED

    def test_get_circuit_breaker_returns_existing(self) -> None:
        """Test get_circuit_breaker returns existing breaker."""
        breaker1 = get_circuit_breaker("api-client")
        breaker1.failure_count = 5

        breaker2 = get_circuit_breaker("api-client")
        assert breaker2 is breaker1
        assert breaker2.failure_count == 5

    def test_get_circuit_breaker_with_custom_config(self) -> None:
        """Test get_circuit_breaker with custom configuration."""
        breaker = get_circuit_breaker(
            "custom",
            failure_threshold=10,
            recovery_timeout=120,
            half_open_requests=2,
        )
        assert breaker.failure_threshold == 10
        assert breaker.recovery_timeout == 120
        assert breaker.half_open_requests == 2

    def test_reset_circuit_breaker_success(self) -> None:
        """Test resetting a circuit breaker by name."""
        breaker = get_circuit_breaker("test")
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 5

        result = reset_circuit_breaker("test")

        assert result is True
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0

    def test_reset_circuit_breaker_not_found(self) -> None:
        """Test resetting non-existent circuit breaker."""
        result = reset_circuit_breaker("nonexistent")
        assert result is False

    def test_get_all_circuit_breakers(self) -> None:
        """Test getting all circuit breaker stats."""
        get_circuit_breaker("breaker1")
        get_circuit_breaker("breaker2")
        breaker2 = get_circuit_breaker("breaker2")
        breaker2.failure_count = 3

        all_stats = get_all_circuit_breakers()

        assert "breaker1" in all_stats
        assert "breaker2" in all_stats
        assert all_stats["breaker2"]["failure_count"] == 3

    def test_clear_all_circuit_breakers(self) -> None:
        """Test clearing all circuit breakers."""
        get_circuit_breaker("breaker1")
        get_circuit_breaker("breaker2")

        clear_all_circuit_breakers()

        all_stats = get_all_circuit_breakers()
        assert len(all_stats) == 0


class TestCircuitBreakerEdgeCases:
    """Edge case tests for circuit breaker."""

    @pytest.fixture(autouse=True)
    def setup(self) -> None:
        """Clear circuit breakers before each test."""
        clear_all_circuit_breakers()

    @pytest.mark.asyncio
    async def test_success_resets_failure_count(self) -> None:
        """Test successful call resets failure count."""
        breaker = CircuitBreaker(name="test", failure_threshold=5)

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        async def success_func() -> str:
            return "success"

        # Accumulate some failures
        for _ in range(3):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        assert breaker.failure_count == 3

        # Success should reset count
        await breaker.call(success_func)
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_time_until_retry(self) -> None:
        """Test time until retry calculation."""
        breaker = CircuitBreaker(
            name="test",
            failure_threshold=2,
            recovery_timeout=60,
        )

        async def fail_func() -> str:
            raise CircuitBreakerTestError("error")

        # Open the circuit
        for _ in range(2):
            with pytest.raises(CircuitBreakerTestError):
                await breaker.call(fail_func)

        # Check time until retry
        time_left = breaker._time_until_retry()
        assert 55 <= time_left <= 60  # Should be close to 60

    @pytest.mark.asyncio
    async def test_circuit_breaker_with_async_generator(self) -> None:
        """Test circuit breaker works with various async patterns."""
        breaker = CircuitBreaker(name="test")

        async def async_func_with_args(a: int, b: str) -> dict[str, Any]:
            return {"a": a, "b": b}

        result = await breaker.call(async_func_with_args, 42, b="test")
        assert result == {"a": 42, "b": "test"}

    @pytest.mark.asyncio
    async def test_different_exception_types(self) -> None:
        """Test circuit breaker handles different exception types."""
        breaker = CircuitBreaker(name="test", failure_threshold=3)

        async def make_fail_func(exc: Exception):
            """Create a function that raises the given exception."""

            async def fail_with_exc() -> str:
                raise exc

            return fail_with_exc

        exceptions = [ValueError("val"), TypeError("type"), RuntimeError("runtime")]

        for exc in exceptions:
            fail_func = await make_fail_func(exc)
            with pytest.raises(type(exc)):
                await breaker.call(fail_func)

        assert breaker.failure_count == 3
        assert breaker.state == CircuitState.OPEN

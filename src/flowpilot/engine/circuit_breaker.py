"""Circuit breaker pattern for protecting against cascading failures."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

from .errors import CircuitOpenError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """State of a circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    The circuit breaker tracks failures and opens when the failure threshold
    is reached, preventing further calls until a recovery timeout expires.

    States:
        - CLOSED: Normal operation, requests pass through
        - OPEN: Circuit is open, requests are rejected immediately
        - HALF_OPEN: Testing recovery, limited requests allowed

    Example:
        ```python
        breaker = get_circuit_breaker("claude-api")
        result = await breaker.call(api_call, arg1, arg2)
        ```
    """

    name: str
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: int = 60  # Seconds before trying again
    half_open_requests: int = 1  # Requests to allow in half-open

    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    half_open_count: int = field(default=0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def call(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function through circuit breaker.

        Args:
            func: Async function to call.
            *args: Positional arguments for func.
            **kwargs: Keyword arguments for func.

        Returns:
            Result of func.

        Raises:
            CircuitOpenError: If circuit is open.
            Exception: Any exception from func.
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    logger.info(f"Circuit {self.name}: transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_count = 0
                else:
                    time_left = self._time_until_retry()
                    raise CircuitOpenError(f"Circuit {self.name} is open. Retry after {time_left}s")

            if self.state == CircuitState.HALF_OPEN:
                if self.half_open_count >= self.half_open_requests:
                    raise CircuitOpenError(
                        f"Circuit {self.name} is half-open, max test requests reached"
                    )
                self.half_open_count += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit {self.name}: recovery successful, transitioning to CLOSED")
                self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count += 1

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now(UTC)

            if self.state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit {self.name}: recovery failed, transitioning to OPEN")
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.failure_threshold:
                logger.warning(
                    f"Circuit {self.name}: failure threshold reached ({self.failure_count}), "
                    f"transitioning to OPEN"
                )
                self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try again."""
        if not self.last_failure_time:
            return True
        elapsed = (datetime.now(UTC) - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout

    def _time_until_retry(self) -> int:
        """Seconds until circuit can be tested."""
        if not self.last_failure_time:
            return 0
        elapsed = (datetime.now(UTC) - self.last_failure_time).total_seconds()
        return max(0, int(self.recovery_timeout - elapsed))

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.half_open_count = 0

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "time_until_retry": self._time_until_retry() if self.state == CircuitState.OPEN else 0,
        }


# Global circuit breakers for shared resources
_circuit_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = asyncio.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    half_open_requests: int = 1,
) -> CircuitBreaker:
    """Get or create a circuit breaker.

    Args:
        name: Unique name for the circuit breaker.
        failure_threshold: Number of failures before opening.
        recovery_timeout: Seconds before testing recovery.
        half_open_requests: Number of test requests in half-open state.

    Returns:
        CircuitBreaker instance.
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            half_open_requests=half_open_requests,
        )
    return _circuit_breakers[name]


def reset_circuit_breaker(name: str) -> bool:
    """Reset a circuit breaker by name.

    Args:
        name: Name of the circuit breaker to reset.

    Returns:
        True if reset, False if not found.
    """
    if name in _circuit_breakers:
        _circuit_breakers[name].reset()
        return True
    return False


def get_all_circuit_breakers() -> dict[str, dict[str, Any]]:
    """Get stats for all circuit breakers."""
    return {name: cb.get_stats() for name, cb in _circuit_breakers.items()}


def clear_all_circuit_breakers() -> None:
    """Clear all circuit breakers (for testing)."""
    _circuit_breakers.clear()

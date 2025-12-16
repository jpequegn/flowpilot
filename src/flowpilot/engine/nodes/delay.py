"""Delay node executor for FlowPilot."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from flowpilot.engine.context import NodeResult
from flowpilot.engine.executor import ExecutorRegistry, NodeExecutor

if TYPE_CHECKING:
    from flowpilot.engine.context import ExecutionContext
    from flowpilot.models import DelayNode

logger = logging.getLogger(__name__)

# Duration parsing pattern: number followed by unit (s, m, h, d)
DURATION_PATTERN = re.compile(
    r"^(\d+(?:\.\d+)?)\s*(s|sec|second|seconds|m|min|minute|minutes|h|hr|hour|hours|d|day|days)$",
    re.IGNORECASE,
)

# Unit multipliers in seconds
UNIT_MULTIPLIERS = {
    "s": 1,
    "sec": 1,
    "second": 1,
    "seconds": 1,
    "m": 60,
    "min": 60,
    "minute": 60,
    "minutes": 60,
    "h": 3600,
    "hr": 3600,
    "hour": 3600,
    "hours": 3600,
    "d": 86400,
    "day": 86400,
    "days": 86400,
}


@ExecutorRegistry.register("delay")
class DelayExecutor(NodeExecutor):
    """Execute delay/wait operations."""

    async def execute(
        self,
        node: DelayNode,  # type: ignore[override]
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute a delay node.

        The delay executor waits for the specified duration or until a target time.

        Args:
            node: The delay node to execute.
            context: The execution context.

        Returns:
            NodeResult with delay execution results.
        """
        started_at = datetime.now(UTC)

        try:
            # Determine wait duration
            if node.duration:
                seconds = self._parse_duration(node.duration)
                wait_type = "duration"
            elif node.until:
                seconds = self._parse_until(node.until, context)
                wait_type = "until"
            else:
                return NodeResult(
                    status="error",
                    error_message="Either 'duration' or 'until' must be specified",
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                )

            if seconds < 0:
                # Target time already passed
                return NodeResult(
                    status="success",
                    output="Target time already passed, no wait needed",
                    data={
                        "requested_seconds": seconds,
                        "actual_seconds": 0,
                        "wait_type": wait_type,
                        "skipped": True,
                    },
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                )

            logger.debug(f"Delay {node.id}: waiting {seconds:.2f} seconds ({wait_type})")

            try:
                await asyncio.sleep(seconds)
            except asyncio.CancelledError:
                actual_waited = (datetime.now(UTC) - started_at).total_seconds()
                logger.debug(f"Delay {node.id}: cancelled after {actual_waited:.2f} seconds")
                return NodeResult(
                    status="skipped",
                    output=f"Delay cancelled after {actual_waited:.2f} seconds",
                    error_message="Delay was cancelled",
                    data={
                        "requested_seconds": seconds,
                        "actual_seconds": actual_waited,
                        "wait_type": wait_type,
                        "cancelled": True,
                    },
                    duration_ms=self._duration_ms(started_at),
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                )

            actual_waited = (datetime.now(UTC) - started_at).total_seconds()
            logger.debug(f"Delay {node.id}: completed after {actual_waited:.2f} seconds")

            return NodeResult(
                status="success",
                output=f"Waited {actual_waited:.2f} seconds",
                data={
                    "requested_seconds": seconds,
                    "actual_seconds": actual_waited,
                    "wait_type": wait_type,
                },
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )

        except ValueError as e:
            return NodeResult(
                status="error",
                error_message=f"Delay configuration error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )
        except Exception as e:
            logger.exception(f"Delay {node.id}: unexpected error")
            return NodeResult(
                status="error",
                error_message=f"Delay error: {e}",
                duration_ms=self._duration_ms(started_at),
                started_at=started_at,
                finished_at=datetime.now(UTC),
            )

    def _parse_duration(self, duration: str) -> float:
        """Parse duration string to seconds.

        Supports formats like:
        - "30s", "30 sec", "30 seconds"
        - "5m", "5 min", "5 minutes"
        - "2h", "2 hr", "2 hours"
        - "1d", "1 day", "1 days"

        Args:
            duration: Duration string to parse.

        Returns:
            Number of seconds.

        Raises:
            ValueError: If duration format is invalid.
        """
        duration = duration.strip()
        match = DURATION_PATTERN.match(duration)

        if not match:
            raise ValueError(
                f"Invalid duration format: '{duration}'. Use formats like '30s', '5m', '2h', '1d'"
            )

        value = float(match.group(1))
        unit = match.group(2).lower()

        return value * UNIT_MULTIPLIERS[unit]

    def _parse_until(self, until: str, context: ExecutionContext) -> float:
        """Parse until string to seconds to wait.

        Supports:
        - ISO datetime strings (e.g., "2024-01-15T10:30:00")
        - Template expressions that resolve to datetime strings

        Args:
            until: Until string or template expression.
            context: Execution context for template resolution.

        Returns:
            Number of seconds to wait (can be negative if time passed).

        Raises:
            ValueError: If until format is invalid.
        """
        # Try to resolve as template if it contains template syntax
        resolved = until.strip()
        if "{{" in until or "{%" in until:
            from flowpilot.engine.template import TemplateEngine

            engine = TemplateEngine()
            resolved = engine.render(until, context.get_template_context())

        # Try parsing as ISO datetime
        try:
            # Handle both aware and naive datetimes
            target = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
            if target.tzinfo is None:
                # Assume UTC for naive datetimes
                target = target.replace(tzinfo=UTC)

            now = datetime.now(UTC)
            return (target - now).total_seconds()
        except ValueError:
            pass

        # Try parsing as just a time (for today)
        try:
            # Parse time-only formats like "14:30" or "14:30:00"
            time_match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", resolved)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                second = int(time_match.group(3) or 0)

                now = datetime.now(UTC)
                target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)

                # If target time has passed today, wait until tomorrow
                if target <= now:
                    from datetime import timedelta

                    target = target + timedelta(days=1)

                return (target - now).total_seconds()
        except (ValueError, AttributeError):
            pass

        raise ValueError(
            f"Cannot parse 'until' value: '{resolved}'. "
            "Use ISO datetime format (e.g., '2024-01-15T10:30:00') "
            "or time format (e.g., '14:30')"
        )

    @staticmethod
    def _duration_ms(started_at: datetime) -> int:
        """Calculate duration in milliseconds."""
        return int((datetime.now(UTC) - started_at).total_seconds() * 1000)

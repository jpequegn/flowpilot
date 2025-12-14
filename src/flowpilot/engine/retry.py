"""Retry logic for FlowPilot node execution."""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import TYPE_CHECKING

from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from flowpilot.models import RetryConfig

from .errors import (
    ErrorCategory,
    FlowPilotError,
    classify_error_message,
)

if TYPE_CHECKING:
    from flowpilot.models import BaseNode

    from .context import ExecutionContext, NodeResult
    from .executor import NodeExecutor

logger = logging.getLogger(__name__)


class RetryExecutor:
    """Wraps node execution with retry logic."""

    def __init__(self, default_config: RetryConfig | None = None) -> None:
        """Initialize retry executor.

        Args:
            default_config: Default retry configuration if node doesn't specify one.
        """
        self.default_config = default_config or RetryConfig()

    async def execute_with_retry(
        self,
        executor: NodeExecutor,
        node: BaseNode,
        context: ExecutionContext,
    ) -> NodeResult:
        """Execute node with retry logic.

        Args:
            executor: The node executor to use.
            node: The node to execute.
            context: The execution context.

        Returns:
            NodeResult with execution outcome.
        """
        from .context import NodeResult

        retry_config = node.retry or self.default_config
        attempts: list[dict] = []
        last_error: Exception | None = None

        def should_retry(exc: BaseException) -> bool:
            """Determine if we should retry based on error category.

            Note: retry_if_exception passes the exception directly, not RetryCallState.
            """
            if isinstance(exc, FlowPilotError):
                if not exc.retryable:
                    return False
                if exc.category == ErrorCategory.TRANSIENT:
                    return retry_config.retry_on_transient
                if exc.category == ErrorCategory.RESOURCE:
                    return retry_config.retry_on_resource
                # PERMANENT and UNKNOWN: PERMANENT should not retry
                return exc.category != ErrorCategory.PERMANENT

            # Unknown exception type - retry
            return True

        async def attempt_execution() -> NodeResult:
            nonlocal last_error
            start = datetime.now()

            try:
                result = await executor.execute(node, context)

                # Check if result indicates retryable error
                if result.status == "error" and result.error_message:
                    category, retryable, retry_after = classify_error_message(result.error_message)

                    if retryable:
                        raise FlowPilotError(
                            message=result.error_message,
                            category=category,
                            node_id=node.id,
                            retryable=True,
                            retry_after=retry_after,
                        )

                return result

            except FlowPilotError:
                raise
            except Exception as e:
                last_error = e
                duration_ms = int((datetime.now() - start).total_seconds() * 1000)
                attempts.append(
                    {
                        "timestamp": start.isoformat(),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration_ms": duration_ms,
                    }
                )

                # Classify the exception
                category, retryable, retry_after = classify_error_message(str(e))

                raise FlowPilotError(
                    message=str(e),
                    category=category,
                    node_id=node.id,
                    retryable=retryable,
                    retry_after=retry_after,
                ) from e

        try:
            # Configure tenacity retry
            retryer = AsyncRetrying(
                stop=stop_after_attempt(retry_config.max_attempts),
                wait=wait_exponential_jitter(
                    initial=retry_config.initial_delay,
                    max=retry_config.max_delay,
                    exp_base=retry_config.exponential_base,
                    jitter=retry_config.max_delay / 2 if retry_config.jitter else 0,
                ),
                retry=retry_if_exception(should_retry),
                reraise=True,
            )

            async for attempt in retryer:
                with attempt:
                    logger.debug(
                        f"Executing node {node.id}, attempt {attempt.retry_state.attempt_number}"
                    )
                    result = await attempt_execution()

                    # Record successful attempt
                    if attempts or attempt.retry_state.attempt_number > 1:
                        result.data["retry_attempts"] = len(attempts) + 1
                        result.data["retried"] = True

                    return result

            # Should not reach here, but return error just in case
            return NodeResult.error("Retry logic error: no result produced")

        except FlowPilotError as e:
            # All retries exhausted
            total_duration = sum(a["duration_ms"] for a in attempts)

            error_result = NodeResult.error(
                error_msg=f"All {retry_config.max_attempts} attempts failed. Last error: {e.message}",
                started_at=datetime.fromisoformat(attempts[0]["timestamp"]) if attempts else None,
            )
            error_result.data = {
                "attempts": attempts,
                "total_attempts": len(attempts),
                "final_error_category": e.category.value,
                "total_duration_ms": total_duration,
            }
            return error_result

        except Exception as e:
            # Unexpected error
            return NodeResult.error(
                error_msg=f"Unexpected error during retry: {e!s}",
            )


def calculate_backoff(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    jitter: bool,
    retry_after: int | None = None,
) -> float:
    """Calculate delay before next retry.

    Args:
        attempt: Current attempt number (0-indexed).
        initial_delay: Initial delay in seconds.
        max_delay: Maximum delay in seconds.
        exponential_base: Base for exponential backoff.
        jitter: Whether to add randomness.
        retry_after: Optional server-specified retry delay.

    Returns:
        Delay in seconds.
    """
    if retry_after:
        return float(retry_after)

    delay = min(initial_delay * (exponential_base**attempt), max_delay)

    if jitter:
        delay = delay * (0.5 + random.random())

    return delay

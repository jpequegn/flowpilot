"""Error classification and handling for FlowPilot workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorCategory(str, Enum):
    """Classification of errors for handling decisions."""

    TRANSIENT = "transient"  # Retry: rate limits, timeouts, network
    PERMANENT = "permanent"  # Don't retry: auth, validation, not found
    RESOURCE = "resource"  # Retry with backoff: capacity, quota
    UNKNOWN = "unknown"  # Retry once, then fail


@dataclass
class FlowPilotError(Exception):
    """Base error with classification and context."""

    message: str
    category: ErrorCategory
    node_id: str | None = None
    retryable: bool = True
    retry_after: int | None = None  # Seconds to wait before retry
    context: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"[{self.category.value}] {self.message}"

    def __post_init__(self) -> None:
        # Call Exception.__init__ with the message
        super().__init__(self.message)


@dataclass
class ClaudeAPIError(FlowPilotError):
    """Errors from Claude API calls."""

    pass


@dataclass
class ClaudeCLIError(FlowPilotError):
    """Errors from Claude CLI execution."""

    pass


@dataclass
class NodeExecutionError(FlowPilotError):
    """Errors during node execution."""

    pass


@dataclass
class WorkflowError(FlowPilotError):
    """Workflow-level errors."""

    pass


@dataclass
class CircuitOpenError(FlowPilotError):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            category=ErrorCategory.RESOURCE,
            retryable=True,
        )


def classify_anthropic_error(error: Exception) -> tuple[ErrorCategory, bool, int | None]:
    """Classify Anthropic SDK errors.

    Args:
        error: The exception from Anthropic SDK.

    Returns:
        Tuple of (category, retryable, retry_after_seconds).
    """
    try:
        import anthropic
    except ImportError:
        return ErrorCategory.UNKNOWN, True, 5

    if isinstance(error, anthropic.RateLimitError):
        # Try to get retry_after from headers or response
        retry_after = 60
        if hasattr(error, "response") and error.response:
            headers = getattr(error.response, "headers", {})
            if "retry-after" in headers:
                import contextlib

                with contextlib.suppress(ValueError, TypeError):
                    retry_after = int(headers["retry-after"])
        return ErrorCategory.RESOURCE, True, retry_after

    if isinstance(error, anthropic.APIConnectionError):
        return ErrorCategory.TRANSIENT, True, 5

    if isinstance(error, anthropic.APITimeoutError):
        return ErrorCategory.TRANSIENT, True, 10

    if isinstance(error, anthropic.AuthenticationError):
        return ErrorCategory.PERMANENT, False, None

    if isinstance(error, anthropic.BadRequestError):
        return ErrorCategory.PERMANENT, False, None

    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return ErrorCategory.TRANSIENT, True, 30
        return ErrorCategory.PERMANENT, False, None

    return ErrorCategory.UNKNOWN, True, 5


def classify_cli_error(exit_code: int, stderr: str) -> tuple[ErrorCategory, bool]:
    """Classify Claude CLI errors.

    Args:
        exit_code: The exit code from the CLI process.
        stderr: The stderr output from the CLI.

    Returns:
        Tuple of (category, retryable).
    """
    stderr_lower = stderr.lower()

    # Rate limit indicators
    if "rate limit" in stderr_lower or "too many requests" in stderr_lower:
        return ErrorCategory.RESOURCE, True

    # Auth issues
    if "unauthorized" in stderr_lower or "authentication" in stderr_lower:
        return ErrorCategory.PERMANENT, False

    # Timeout
    if exit_code == 124 or "timeout" in stderr_lower:
        return ErrorCategory.TRANSIENT, True

    # Network errors
    if "connection" in stderr_lower or "network" in stderr_lower:
        return ErrorCategory.TRANSIENT, True

    # Unknown non-zero exit
    if exit_code != 0:
        return ErrorCategory.UNKNOWN, True

    return ErrorCategory.PERMANENT, False


def classify_http_error(
    status_code: int, response_text: str = ""
) -> tuple[ErrorCategory, bool, int | None]:
    """Classify HTTP response errors.

    Args:
        status_code: HTTP status code.
        response_text: Response body text.

    Returns:
        Tuple of (category, retryable, retry_after_seconds).
    """
    response_lower = response_text.lower()

    # Rate limiting
    if status_code == 429:
        # Try to parse Retry-After from response
        retry_after = 60
        if "retry-after" in response_lower:
            import re

            match = re.search(r"retry.?after[:\s]+(\d+)", response_lower)
            if match:
                retry_after = int(match.group(1))
        return ErrorCategory.RESOURCE, True, retry_after

    # Server errors (5xx) - transient, retry
    if 500 <= status_code < 600:
        return ErrorCategory.TRANSIENT, True, 5

    # Client errors
    if status_code == 401 or status_code == 403:
        return ErrorCategory.PERMANENT, False, None

    if status_code == 404:
        return ErrorCategory.PERMANENT, False, None

    if status_code == 400:
        return ErrorCategory.PERMANENT, False, None

    if status_code == 408:  # Request Timeout
        return ErrorCategory.TRANSIENT, True, 5

    # Other 4xx - generally not retryable
    if 400 <= status_code < 500:
        return ErrorCategory.PERMANENT, False, None

    return ErrorCategory.UNKNOWN, True, 5


def classify_error_message(error_message: str) -> tuple[ErrorCategory, bool, int | None]:
    """Classify errors based on error message content.

    Args:
        error_message: The error message string.

    Returns:
        Tuple of (category, retryable, retry_after_seconds).
    """
    error_lower = error_message.lower()

    # Rate limiting
    if any(kw in error_lower for kw in ["rate limit", "429", "too many requests", "quota"]):
        return ErrorCategory.RESOURCE, True, 60

    # Timeout
    if any(kw in error_lower for kw in ["timeout", "timed out", "deadline exceeded"]):
        return ErrorCategory.TRANSIENT, True, 5

    # Network errors
    if any(kw in error_lower for kw in ["connection", "network", "dns", "unreachable", "refused"]):
        return ErrorCategory.TRANSIENT, True, 5

    # Auth errors
    if any(
        kw in error_lower
        for kw in ["unauthorized", "authentication", "forbidden", "invalid key", "api key"]
    ):
        return ErrorCategory.PERMANENT, False, None

    # Validation errors
    if any(kw in error_lower for kw in ["validation", "invalid", "malformed", "bad request"]):
        return ErrorCategory.PERMANENT, False, None

    # Not found
    if any(kw in error_lower for kw in ["not found", "does not exist", "404"]):
        return ErrorCategory.PERMANENT, False, None

    # Server errors
    if any(
        kw in error_lower for kw in ["server error", "internal error", "500", "502", "503", "504"]
    ):
        return ErrorCategory.TRANSIENT, True, 30

    return ErrorCategory.UNKNOWN, True, 5

"""Tests for error classification and handling."""

from __future__ import annotations

from flowpilot.engine.errors import (
    ClaudeAPIError,
    ClaudeCLIError,
    ErrorCategory,
    FlowPilotError,
    NodeExecutionError,
    WorkflowError,
    classify_cli_error,
    classify_error_message,
    classify_http_error,
)


class TestErrorCategory:
    """Tests for error categories."""

    def test_error_categories_exist(self) -> None:
        """Test all error categories are defined."""
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.PERMANENT.value == "permanent"
        assert ErrorCategory.RESOURCE.value == "resource"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestFlowPilotError:
    """Tests for FlowPilotError base class."""

    def test_create_error(self) -> None:
        """Test creating a FlowPilotError."""
        error = FlowPilotError(
            message="Test error",
            category=ErrorCategory.TRANSIENT,
        )
        assert error.message == "Test error"
        assert error.category == ErrorCategory.TRANSIENT
        assert error.retryable is True
        assert error.node_id is None

    def test_error_str(self) -> None:
        """Test error string representation."""
        error = FlowPilotError(
            message="Something failed",
            category=ErrorCategory.PERMANENT,
        )
        assert str(error) == "[permanent] Something failed"

    def test_error_with_context(self) -> None:
        """Test error with context data."""
        error = FlowPilotError(
            message="API error",
            category=ErrorCategory.RESOURCE,
            node_id="my-node",
            retry_after=60,
            context={"status_code": 429},
        )
        assert error.node_id == "my-node"
        assert error.retry_after == 60
        assert error.context["status_code"] == 429


class TestSpecializedErrors:
    """Tests for specialized error classes."""

    def test_claude_api_error(self) -> None:
        """Test ClaudeAPIError."""
        error = ClaudeAPIError(
            message="Rate limited",
            category=ErrorCategory.RESOURCE,
            retry_after=30,
        )
        assert isinstance(error, FlowPilotError)
        assert error.retry_after == 30

    def test_claude_cli_error(self) -> None:
        """Test ClaudeCLIError."""
        error = ClaudeCLIError(
            message="CLI timeout",
            category=ErrorCategory.TRANSIENT,
        )
        assert isinstance(error, FlowPilotError)
        assert error.category == ErrorCategory.TRANSIENT

    def test_node_execution_error(self) -> None:
        """Test NodeExecutionError."""
        error = NodeExecutionError(
            message="Node failed",
            category=ErrorCategory.PERMANENT,
            node_id="failed-node",
        )
        assert error.node_id == "failed-node"

    def test_workflow_error(self) -> None:
        """Test WorkflowError."""
        error = WorkflowError(
            message="Workflow failed",
            category=ErrorCategory.UNKNOWN,
        )
        assert isinstance(error, FlowPilotError)


class TestClassifyCLIError:
    """Tests for classify_cli_error function."""

    def test_rate_limit_in_stderr(self) -> None:
        """Test rate limit detection."""
        category, retryable = classify_cli_error(1, "Error: rate limit exceeded")
        assert category == ErrorCategory.RESOURCE
        assert retryable is True

    def test_too_many_requests(self) -> None:
        """Test too many requests detection."""
        category, retryable = classify_cli_error(1, "Too many requests")
        assert category == ErrorCategory.RESOURCE
        assert retryable is True

    def test_unauthorized(self) -> None:
        """Test unauthorized detection."""
        category, retryable = classify_cli_error(1, "Error: Unauthorized access")
        assert category == ErrorCategory.PERMANENT
        assert retryable is False

    def test_authentication_error(self) -> None:
        """Test authentication error detection."""
        category, retryable = classify_cli_error(1, "Authentication failed")
        assert category == ErrorCategory.PERMANENT
        assert retryable is False

    def test_timeout_exit_code(self) -> None:
        """Test timeout by exit code."""
        category, retryable = classify_cli_error(124, "")
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True

    def test_timeout_in_stderr(self) -> None:
        """Test timeout in stderr."""
        category, retryable = classify_cli_error(1, "Request timeout")
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True

    def test_connection_error(self) -> None:
        """Test connection error detection."""
        category, retryable = classify_cli_error(1, "Connection refused")
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True

    def test_network_error(self) -> None:
        """Test network error detection."""
        category, retryable = classify_cli_error(1, "Network unreachable")
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True

    def test_unknown_nonzero_exit(self) -> None:
        """Test unknown error with non-zero exit."""
        category, retryable = classify_cli_error(1, "Some random error")
        assert category == ErrorCategory.UNKNOWN
        assert retryable is True

    def test_zero_exit_code(self) -> None:
        """Test zero exit code is permanent."""
        category, retryable = classify_cli_error(0, "")
        assert category == ErrorCategory.PERMANENT
        assert retryable is False


class TestClassifyHTTPError:
    """Tests for classify_http_error function."""

    def test_rate_limit_429(self) -> None:
        """Test 429 rate limit."""
        category, retryable, retry_after = classify_http_error(429)
        assert category == ErrorCategory.RESOURCE
        assert retryable is True
        assert retry_after == 60

    def test_rate_limit_with_retry_after(self) -> None:
        """Test 429 with retry-after in response."""
        _category, _retryable, retry_after = classify_http_error(429, "retry-after: 30 seconds")
        assert retry_after == 30

    def test_server_error_500(self) -> None:
        """Test 500 server error."""
        category, retryable, retry_after = classify_http_error(500)
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True
        assert retry_after == 5

    def test_server_error_502(self) -> None:
        """Test 502 bad gateway."""
        category, retryable, _ = classify_http_error(502)
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True

    def test_server_error_503(self) -> None:
        """Test 503 service unavailable."""
        category, retryable, _ = classify_http_error(503)
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True

    def test_unauthorized_401(self) -> None:
        """Test 401 unauthorized."""
        category, retryable, _ = classify_http_error(401)
        assert category == ErrorCategory.PERMANENT
        assert retryable is False

    def test_forbidden_403(self) -> None:
        """Test 403 forbidden."""
        category, retryable, _ = classify_http_error(403)
        assert category == ErrorCategory.PERMANENT
        assert retryable is False

    def test_not_found_404(self) -> None:
        """Test 404 not found."""
        category, retryable, _ = classify_http_error(404)
        assert category == ErrorCategory.PERMANENT
        assert retryable is False

    def test_bad_request_400(self) -> None:
        """Test 400 bad request."""
        category, retryable, _ = classify_http_error(400)
        assert category == ErrorCategory.PERMANENT
        assert retryable is False

    def test_request_timeout_408(self) -> None:
        """Test 408 request timeout."""
        category, retryable, _ = classify_http_error(408)
        assert category == ErrorCategory.TRANSIENT
        assert retryable is True


class TestClassifyErrorMessage:
    """Tests for classify_error_message function."""

    def test_rate_limit_messages(self) -> None:
        """Test rate limit message detection."""
        messages = [
            "Rate limit exceeded",
            "Error 429: too many requests",
            "Quota exhausted",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.RESOURCE
            assert retryable is True

    def test_timeout_messages(self) -> None:
        """Test timeout message detection."""
        messages = [
            "Request timeout",
            "Operation timed out",
            "Deadline exceeded",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.TRANSIENT
            assert retryable is True

    def test_network_messages(self) -> None:
        """Test network error message detection."""
        messages = [
            "Connection refused",
            "Network unreachable",
            "DNS resolution failed",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.TRANSIENT
            assert retryable is True

    def test_auth_messages(self) -> None:
        """Test auth error message detection."""
        messages = [
            "Unauthorized",
            "Authentication failed",
            "Forbidden access",
            "Invalid API key",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.PERMANENT
            assert retryable is False

    def test_validation_messages(self) -> None:
        """Test validation error message detection."""
        messages = [
            "Validation error",
            "Invalid input",
            "Malformed request",
            "Bad request",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.PERMANENT
            assert retryable is False

    def test_not_found_messages(self) -> None:
        """Test not found message detection."""
        messages = [
            "Resource not found",
            "File does not exist",
            "404 error",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.PERMANENT
            assert retryable is False

    def test_server_error_messages(self) -> None:
        """Test server error message detection."""
        messages = [
            "Internal server error",
            "500 error occurred",
            "502 bad gateway",
            "503 service unavailable",
            "504 gateway timeout",
        ]
        for msg in messages:
            category, retryable, _ = classify_error_message(msg)
            assert category == ErrorCategory.TRANSIENT
            assert retryable is True

    def test_unknown_message(self) -> None:
        """Test unknown message classification."""
        category, retryable, retry_after = classify_error_message("Something weird happened")
        assert category == ErrorCategory.UNKNOWN
        assert retryable is True
        assert retry_after == 5

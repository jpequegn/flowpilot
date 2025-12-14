"""Tests for error reporter and aggregation."""

from __future__ import annotations

from datetime import timedelta

from flowpilot.engine.error_reporter import (
    ErrorReport,
    ErrorReporter,
    NodeError,
    get_error_reporter,
)


class TestNodeError:
    """Tests for NodeError dataclass."""

    def test_create_node_error(self) -> None:
        """Test creating a NodeError."""
        error = NodeError(
            node_id="test-node",
            error="Something went wrong",
            category="transient",
            attempts=3,
        )
        assert error.node_id == "test-node"
        assert error.error == "Something went wrong"
        assert error.category == "transient"
        assert error.attempts == 3
        assert error.fallback_used is False
        assert error.continued is False

    def test_node_error_with_fallback(self) -> None:
        """Test NodeError with fallback used."""
        error = NodeError(
            node_id="test-node",
            error="Primary failed",
            category="transient",
            attempts=2,
            fallback_used=True,
        )
        assert error.fallback_used is True

    def test_node_error_with_continued(self) -> None:
        """Test NodeError with workflow continued."""
        error = NodeError(
            node_id="test-node",
            error="Non-critical failure",
            category="unknown",
            attempts=1,
            continued=True,
        )
        assert error.continued is True

    def test_node_error_to_dict(self) -> None:
        """Test NodeError to_dict conversion."""
        error = NodeError(
            node_id="test-node",
            error="Test error",
            category="permanent",
            attempts=1,
            fallback_used=True,
            continued=False,
        )
        data = error.to_dict()

        assert data["node_id"] == "test-node"
        assert data["error"] == "Test error"
        assert data["category"] == "permanent"
        assert data["attempts"] == 1
        assert data["fallback_used"] is True
        assert data["continued"] is False
        assert "timestamp" in data


class TestErrorReport:
    """Tests for ErrorReport dataclass."""

    def test_create_error_report(self) -> None:
        """Test creating an ErrorReport."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=10,
        )
        assert report.execution_id == "exec-123"
        assert report.workflow_name == "test-workflow"
        assert report.total_nodes == 10
        assert report.executed_nodes == 0
        assert report.failed_nodes == 0
        assert len(report.errors) == 0

    def test_add_error(self) -> None:
        """Test adding an error to report."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=5,
        )

        report.add_error(
            node_id="node-1",
            error="Test error",
            category="transient",
            attempts=3,
        )

        assert report.failed_nodes == 1
        assert len(report.errors) == 1
        assert report.errors[0].node_id == "node-1"

    def test_add_multiple_errors(self) -> None:
        """Test adding multiple errors."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=5,
        )

        report.add_error(node_id="node-1", error="Error 1", category="transient", attempts=1)
        report.add_error(node_id="node-2", error="Error 2", category="permanent", attempts=1)
        report.add_error(
            node_id="node-3", error="Error 3", category="resource", attempts=5, fallback_used=True
        )

        assert report.failed_nodes == 3
        assert len(report.errors) == 3

    def test_record_execution(self) -> None:
        """Test recording node execution."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=5,
        )

        report.record_execution(success=True)
        report.record_execution(success=True)
        report.record_execution(success=False)

        assert report.executed_nodes == 3
        assert report.failed_nodes == 1

    def test_finish_report(self) -> None:
        """Test finishing a report."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )
        assert report.finished_at is None

        report.finish()

        assert report.finished_at is not None

    def test_success_rate_all_success(self) -> None:
        """Test success rate with all successes."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )
        report.executed_nodes = 10
        report.failed_nodes = 0

        assert report.success_rate == 1.0

    def test_success_rate_partial_failure(self) -> None:
        """Test success rate with some failures."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )
        report.executed_nodes = 10
        report.failed_nodes = 3

        assert report.success_rate == 0.7

    def test_success_rate_no_executions(self) -> None:
        """Test success rate with no executions."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )
        assert report.success_rate == 0.0

    def test_has_errors(self) -> None:
        """Test has_errors property."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )
        assert report.has_errors is False

        report.add_error(node_id="node-1", error="Error", category="unknown", attempts=1)
        assert report.has_errors is True

    def test_duration_ms(self) -> None:
        """Test duration_ms calculation."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )
        assert report.duration_ms is None

        report.finished_at = report.started_at + timedelta(milliseconds=1500)
        assert report.duration_ms == 1500

    def test_to_dict(self) -> None:
        """Test to_dict conversion."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=5,
        )
        report.executed_nodes = 4
        # add_error increments failed_nodes, so set executed first
        report.add_error(node_id="node-1", error="Test error", category="transient", attempts=2)
        report.finish()

        data = report.to_dict()

        assert data["execution_id"] == "exec-123"
        assert data["workflow_name"] == "test-workflow"
        assert data["summary"]["total_nodes"] == 5
        assert data["summary"]["executed_nodes"] == 4
        assert data["summary"]["failed_nodes"] == 1
        # success_rate = (executed - failed) / executed = (4-1)/4 = 0.75
        assert data["summary"]["success_rate"] == 0.75
        assert data["summary"]["has_errors"] is True
        assert len(data["errors"]) == 1
        assert data["timing"]["started_at"] is not None
        assert data["timing"]["finished_at"] is not None

    def test_to_markdown(self) -> None:
        """Test to_markdown generation."""
        report = ErrorReport(
            execution_id="exec-12345678",
            workflow_name="test-workflow",
            total_nodes=5,
        )
        report.executed_nodes = 4
        # Note: add_error increments failed_nodes, so this will set it to 2
        report.add_error(
            node_id="node-1", error="Connection timeout", category="transient", attempts=3
        )
        report.add_error(
            node_id="node-2",
            error="Auth failed",
            category="permanent",
            attempts=1,
            fallback_used=True,
        )
        report.finish()

        markdown = report.to_markdown()

        assert "# Error Report: test-workflow" in markdown
        assert "exec-123" in markdown  # First 8 chars of "exec-12345678"
        assert "## Summary" in markdown
        assert "Total Nodes | 5" in markdown
        assert "Failed | 2" in markdown  # 2 errors added = 2 failed
        assert "## Errors" in markdown
        assert "node-1" in markdown
        assert "Connection timeout" in markdown
        assert "node-2" in markdown
        assert "**Fallback**: Used" in markdown

    def test_to_markdown_no_errors(self) -> None:
        """Test to_markdown with no errors."""
        report = ErrorReport(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=5,
        )
        report.executed_nodes = 5
        report.finish()

        markdown = report.to_markdown()

        assert "No errors recorded." in markdown

    def test_to_summary(self) -> None:
        """Test to_summary generation."""
        report = ErrorReport(
            execution_id="exec-12345678",
            workflow_name="test-workflow",
            total_nodes=10,
        )
        report.executed_nodes = 8

        # Success case
        summary = report.to_summary()
        assert "[SUCCESS]" in summary
        assert "test-workflow" in summary
        assert "8/10 nodes" in summary

        # Failure case
        report.add_error(node_id="node-1", error="Error", category="unknown", attempts=1)
        summary = report.to_summary()
        assert "[FAILED]" in summary
        assert "1 errors" in summary


class TestErrorReporter:
    """Tests for ErrorReporter service."""

    def test_create_report(self) -> None:
        """Test creating a new report."""
        reporter = ErrorReporter()

        report = reporter.create_report(
            execution_id="exec-123",
            workflow_name="test-workflow",
            total_nodes=5,
        )

        assert report.execution_id == "exec-123"
        assert report.workflow_name == "test-workflow"
        assert report.total_nodes == 5

    def test_get_report(self) -> None:
        """Test getting a report by ID."""
        reporter = ErrorReporter()

        created = reporter.create_report(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )

        retrieved = reporter.get_report("exec-123")
        assert retrieved is created

    def test_get_report_not_found(self) -> None:
        """Test getting non-existent report."""
        reporter = ErrorReporter()

        report = reporter.get_report("nonexistent")
        assert report is None

    def test_finish_report(self) -> None:
        """Test finishing a report."""
        reporter = ErrorReporter()

        reporter.create_report(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )

        report = reporter.finish_report("exec-123")

        assert report is not None
        assert report.finished_at is not None

    def test_finish_report_not_found(self) -> None:
        """Test finishing non-existent report."""
        reporter = ErrorReporter()

        report = reporter.finish_report("nonexistent")
        assert report is None

    def test_clear_report(self) -> None:
        """Test clearing a report."""
        reporter = ErrorReporter()

        reporter.create_report(
            execution_id="exec-123",
            workflow_name="test-workflow",
        )

        result = reporter.clear_report("exec-123")
        assert result is True

        report = reporter.get_report("exec-123")
        assert report is None

    def test_clear_report_not_found(self) -> None:
        """Test clearing non-existent report."""
        reporter = ErrorReporter()

        result = reporter.clear_report("nonexistent")
        assert result is False

    def test_get_all_reports(self) -> None:
        """Test getting all reports."""
        reporter = ErrorReporter()

        reporter.create_report(
            execution_id="exec-1",
            workflow_name="workflow-1",
        )
        reporter.create_report(
            execution_id="exec-2",
            workflow_name="workflow-2",
        )

        reports = reporter.get_all_reports()
        assert len(reports) == 2

    def test_clear_all(self) -> None:
        """Test clearing all reports."""
        reporter = ErrorReporter()

        reporter.create_report(execution_id="exec-1", workflow_name="workflow-1")
        reporter.create_report(execution_id="exec-2", workflow_name="workflow-2")

        reporter.clear_all()

        reports = reporter.get_all_reports()
        assert len(reports) == 0


class TestGlobalErrorReporter:
    """Tests for global error reporter instance."""

    def test_get_error_reporter(self) -> None:
        """Test getting global error reporter."""
        reporter1 = get_error_reporter()
        reporter2 = get_error_reporter()

        # Should return same instance
        assert reporter1 is reporter2

    def test_global_reporter_is_error_reporter(self) -> None:
        """Test global reporter is ErrorReporter instance."""
        reporter = get_error_reporter()
        assert isinstance(reporter, ErrorReporter)

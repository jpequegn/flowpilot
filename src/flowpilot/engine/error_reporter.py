"""Error aggregation and reporting for FlowPilot workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class NodeError:
    """Information about a single node error."""

    node_id: str
    error: str
    category: str
    attempts: int
    fallback_used: bool = False
    continued: bool = False
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "node_id": self.node_id,
            "error": self.error,
            "category": self.category,
            "attempts": self.attempts,
            "fallback_used": self.fallback_used,
            "continued": self.continued,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class ErrorReport:
    """Aggregated error information for a workflow execution."""

    execution_id: str
    workflow_name: str
    total_nodes: int = 0
    executed_nodes: int = 0
    failed_nodes: int = 0
    errors: list[NodeError] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None

    def add_error(
        self,
        node_id: str,
        error: str,
        category: str = "unknown",
        attempts: int = 1,
        fallback_used: bool = False,
        continued: bool = False,
    ) -> None:
        """Add an error to the report.

        Args:
            node_id: ID of the failed node.
            error: Error message.
            category: Error category.
            attempts: Number of retry attempts made.
            fallback_used: Whether a fallback node was used.
            continued: Whether workflow continued despite error.
        """
        self.failed_nodes += 1
        self.errors.append(
            NodeError(
                node_id=node_id,
                error=error,
                category=category,
                attempts=attempts,
                fallback_used=fallback_used,
                continued=continued,
            )
        )

    def record_execution(self, success: bool) -> None:
        """Record a node execution.

        Args:
            success: Whether the node succeeded.
        """
        self.executed_nodes += 1
        if not success:
            self.failed_nodes += 1

    def finish(self) -> None:
        """Mark the report as finished."""
        self.finished_at = datetime.now()

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.executed_nodes == 0:
            return 0.0
        return (self.executed_nodes - self.failed_nodes) / self.executed_nodes

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0

    @property
    def duration_ms(self) -> int | None:
        """Get duration in milliseconds."""
        if not self.finished_at:
            return None
        return int((self.finished_at - self.started_at).total_seconds() * 1000)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
            "summary": {
                "total_nodes": self.total_nodes,
                "executed_nodes": self.executed_nodes,
                "failed_nodes": self.failed_nodes,
                "success_rate": self.success_rate,
                "has_errors": self.has_errors,
            },
            "timing": {
                "started_at": self.started_at.isoformat(),
                "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                "duration_ms": self.duration_ms,
            },
            "errors": [e.to_dict() for e in self.errors],
        }

    def to_markdown(self) -> str:
        """Generate markdown error report."""
        lines = [
            f"# Error Report: {self.workflow_name}",
            "",
            f"**Execution ID**: `{self.execution_id[:8]}`",
            f"**Started**: {self.started_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if self.finished_at:
            lines.append(f"**Finished**: {self.finished_at.strftime('%Y-%m-%d %H:%M:%S')}")
            if self.duration_ms:
                lines.append(f"**Duration**: {self.duration_ms}ms")

        lines.extend(
            [
                "",
                "## Summary",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Total Nodes | {self.total_nodes} |",
                f"| Executed | {self.executed_nodes} |",
                f"| Failed | {self.failed_nodes} |",
                f"| Success Rate | {self.success_rate:.1%} |",
                "",
            ]
        )

        if self.errors:
            lines.extend(
                [
                    "## Errors",
                    "",
                ]
            )

            for i, err in enumerate(self.errors, 1):
                lines.append(f"### {i}. {err.node_id}")
                lines.append("")
                lines.append(f"- **Category**: `{err.category}`")
                lines.append(f"- **Attempts**: {err.attempts}")

                if err.fallback_used:
                    lines.append("- **Fallback**: Used")
                if err.continued:
                    lines.append("- **Continued**: Yes (workflow continued)")

                lines.append(f"- **Error**: {err.error}")
                lines.append("")
        else:
            lines.extend(
                [
                    "## Errors",
                    "",
                    "No errors recorded.",
                    "",
                ]
            )

        return "\n".join(lines)

    def to_summary(self) -> str:
        """Generate a brief summary line."""
        status = "SUCCESS" if not self.has_errors else "FAILED"
        error_info = f", {self.failed_nodes} errors" if self.has_errors else ""
        return (
            f"[{status}] {self.workflow_name} ({self.execution_id[:8]}): "
            f"{self.executed_nodes}/{self.total_nodes} nodes{error_info}"
        )


class ErrorReporter:
    """Service for collecting and reporting errors during workflow execution."""

    def __init__(self) -> None:
        """Initialize error reporter."""
        self._reports: dict[str, ErrorReport] = {}

    def create_report(
        self,
        execution_id: str,
        workflow_name: str,
        total_nodes: int = 0,
    ) -> ErrorReport:
        """Create a new error report for an execution.

        Args:
            execution_id: Unique execution identifier.
            workflow_name: Name of the workflow.
            total_nodes: Total number of nodes in the workflow.

        Returns:
            New ErrorReport instance.
        """
        report = ErrorReport(
            execution_id=execution_id,
            workflow_name=workflow_name,
            total_nodes=total_nodes,
        )
        self._reports[execution_id] = report
        return report

    def get_report(self, execution_id: str) -> ErrorReport | None:
        """Get an error report by execution ID.

        Args:
            execution_id: The execution ID to look up.

        Returns:
            ErrorReport if found, None otherwise.
        """
        return self._reports.get(execution_id)

    def finish_report(self, execution_id: str) -> ErrorReport | None:
        """Finish and return a report.

        Args:
            execution_id: The execution ID.

        Returns:
            Finished ErrorReport if found.
        """
        report = self._reports.get(execution_id)
        if report:
            report.finish()
        return report

    def clear_report(self, execution_id: str) -> bool:
        """Remove a report.

        Args:
            execution_id: The execution ID to remove.

        Returns:
            True if removed, False if not found.
        """
        if execution_id in self._reports:
            del self._reports[execution_id]
            return True
        return False

    def get_all_reports(self) -> list[ErrorReport]:
        """Get all stored reports."""
        return list(self._reports.values())

    def clear_all(self) -> None:
        """Clear all reports."""
        self._reports.clear()


# Global error reporter instance
_error_reporter = ErrorReporter()


def get_error_reporter() -> ErrorReporter:
    """Get the global error reporter instance."""
    return _error_reporter

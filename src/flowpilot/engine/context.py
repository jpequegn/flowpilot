"""Execution context for FlowPilot workflows."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass
class NodeResult:
    """Result of executing a single node."""

    status: Literal["success", "error", "skipped", "running", "pending"]
    stdout: str = ""
    stderr: str = ""
    output: Any = None  # Parsed/structured output
    data: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def pending(cls) -> NodeResult:
        """Create a pending result."""
        return cls(status="pending")

    @classmethod
    def running(cls) -> NodeResult:
        """Create a running result."""
        return cls(status="running", started_at=datetime.now())

    @classmethod
    def success(
        cls,
        stdout: str = "",
        stderr: str = "",
        output: Any = None,
        data: dict[str, Any] | None = None,
        started_at: datetime | None = None,
    ) -> NodeResult:
        """Create a success result."""
        finished = datetime.now()
        duration = 0
        if started_at:
            duration = int((finished - started_at).total_seconds() * 1000)
        return cls(
            status="success",
            stdout=stdout,
            stderr=stderr,
            output=output,
            data=data or {},
            duration_ms=duration,
            started_at=started_at,
            finished_at=finished,
        )

    @classmethod
    def error(
        cls,
        error_msg: str,
        stdout: str = "",
        stderr: str = "",
        started_at: datetime | None = None,
    ) -> NodeResult:
        """Create an error result."""
        finished = datetime.now()
        duration = 0
        if started_at:
            duration = int((finished - started_at).total_seconds() * 1000)
        return cls(
            status="error",
            stdout=stdout,
            stderr=stderr,
            error_message=error_msg,
            duration_ms=duration,
            started_at=started_at,
            finished_at=finished,
        )

    @classmethod
    def skipped(cls, reason: str = "") -> NodeResult:
        """Create a skipped result."""
        return cls(status="skipped", error_message=reason if reason else None)


@dataclass
class ExecutionContext:
    """Context for a workflow execution."""

    workflow_name: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    inputs: dict[str, Any] = field(default_factory=dict)
    nodes: dict[str, NodeResult] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)
    finished_at: datetime | None = None
    status: Literal["running", "success", "error", "cancelled"] = "running"

    def get_template_context(self) -> dict[str, Any]:
        """Return context dict for Jinja2 templating."""
        return {
            "inputs": self.inputs,
            "nodes": {
                # Replace hyphens with underscores for template access
                node_id.replace("-", "_"): {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "output": result.output,
                    "data": result.data,
                    "status": result.status,
                }
                for node_id, result in self.nodes.items()
            },
            "env": dict(os.environ),
            "date": lambda fmt: datetime.now().strftime(fmt),
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
        }

    def set_node_result(self, node_id: str, result: NodeResult) -> None:
        """Set the result for a node."""
        self.nodes[node_id] = result

    def get_node_result(self, node_id: str) -> NodeResult | None:
        """Get the result for a node."""
        return self.nodes.get(node_id)

    def mark_finished(self, status: Literal["success", "error", "cancelled"]) -> None:
        """Mark the execution as finished."""
        self.finished_at = datetime.now()
        self.status = status

    @property
    def duration_ms(self) -> int:
        """Total execution duration in milliseconds."""
        end = self.finished_at or datetime.now()
        return int((end - self.started_at).total_seconds() * 1000)

    @property
    def has_errors(self) -> bool:
        """Check if any node has errors."""
        return any(r.status == "error" for r in self.nodes.values())

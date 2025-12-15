"""Execution context for FlowPilot workflows."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


class DotDict(dict[str, Any]):
    """Dictionary that supports attribute-style access.

    This allows expressions like `inputs.items` to access `inputs["items"]`
    instead of the dict's .items() method.

    Keys in the dictionary take precedence over dict methods.
    """

    # Dict methods that we want to preserve access to
    _DICT_METHODS = frozenset(
        {
            "keys",
            "values",
            "get",
            "pop",
            "update",
            "setdefault",
            "clear",
            "copy",
            "fromkeys",
            "popitem",
        }
    )

    def __getattribute__(self, key: str) -> Any:
        """Get attribute, preferring dict keys over methods."""
        # Always allow access to private attributes and our class attributes
        if key.startswith("_") or key == "_DICT_METHODS":
            return super().__getattribute__(key)

        # Check if key exists in dict first (takes precedence)
        try:
            if key in self:
                value = self[key]
                # Recursively wrap nested dicts
                if isinstance(value, dict) and not isinstance(value, DotDict):
                    return DotDict(value)
                return value
        except (KeyError, TypeError):
            pass

        # Fall back to normal attribute lookup (dict methods, etc.)
        return super().__getattribute__(key)

    def __getattr__(self, key: str) -> Any:
        """Get item by attribute access (fallback for missing attributes)."""
        try:
            value = self[key]
            # Recursively wrap nested dicts
            if isinstance(value, dict) and not isinstance(value, DotDict):
                return DotDict(value)
            return value
        except KeyError as e:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{key}'") from e

    def __setattr__(self, key: str, value: Any) -> None:
        """Set item by attribute access."""
        self[key] = value

    def __delattr__(self, key: str) -> None:
        """Delete item by attribute access."""
        try:
            del self[key]
        except KeyError as e:
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{key}'") from e


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
    # Loop variables - available during loop iterations
    loop_variables: dict[str, Any] = field(default_factory=dict)

    def get_template_context(self) -> dict[str, Any]:
        """Return context dict for Jinja2 templating.

        Wraps dictionaries in DotDict to support attribute-style access
        (e.g., `inputs.items` instead of `inputs['items']`).
        """
        ctx: dict[str, Any] = {
            "inputs": DotDict(self.inputs),
            "nodes": DotDict(
                {
                    # Replace hyphens with underscores for template access
                    node_id.replace("-", "_"): DotDict(
                        {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "output": result.output,
                            "data": DotDict(result.data) if result.data else {},
                            "status": result.status,
                        }
                    )
                    for node_id, result in self.nodes.items()
                }
            ),
            "env": DotDict(dict(os.environ)),
            "date": lambda fmt: datetime.now().strftime(fmt),
            "execution_id": self.execution_id,
            "workflow_name": self.workflow_name,
        }
        # Add loop variables to template context
        ctx.update(self.loop_variables)
        return ctx

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

    def set_loop_variable(self, name: str, value: Any) -> None:
        """Set a loop variable for use in child node templates.

        Args:
            name: Variable name (e.g., 'item', 'index').
            value: Variable value.
        """
        self.loop_variables[name] = value

    def clear_loop_variables(self, *names: str) -> None:
        """Clear loop variables.

        Args:
            *names: Variable names to clear. If empty, clears all.
        """
        if names:
            for name in names:
                self.loop_variables.pop(name, None)
        else:
            self.loop_variables.clear()

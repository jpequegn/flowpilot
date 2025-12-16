"""Execution API schemas for FlowPilot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NodeExecutionResponse(BaseModel):
    """Response for a node execution."""

    id: int = Field(..., description="Node execution ID")
    node_id: str = Field(..., description="Node identifier")
    node_type: str = Field(..., description="Node type")
    status: str = Field(..., description="Node execution status")
    started_at: datetime | None = Field(default=None, description="Start timestamp")
    finished_at: datetime | None = Field(default=None, description="Finish timestamp")
    duration_ms: int | None = Field(default=None, description="Duration in milliseconds")
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")
    output: str = Field(default="", description="Structured output (JSON)")
    error: str | None = Field(default=None, description="Error message")


class ExecutionListItem(BaseModel):
    """Summary of an execution for list responses."""

    id: str = Field(..., description="Execution ID")
    workflow_name: str = Field(..., description="Workflow name")
    status: str = Field(..., description="Execution status")
    trigger_type: str | None = Field(default=None, description="Trigger type")
    started_at: datetime = Field(..., description="Start timestamp")
    finished_at: datetime | None = Field(default=None, description="Finish timestamp")
    duration_ms: int | None = Field(default=None, description="Duration in milliseconds")


class ExecutionDetail(BaseModel):
    """Detailed execution information."""

    id: str = Field(..., description="Execution ID")
    workflow_name: str = Field(..., description="Workflow name")
    workflow_path: str = Field(..., description="Workflow file path")
    status: str = Field(..., description="Execution status")
    trigger_type: str | None = Field(default=None, description="Trigger type")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Input parameters")
    started_at: datetime = Field(..., description="Start timestamp")
    finished_at: datetime | None = Field(default=None, description="Finish timestamp")
    duration_ms: int | None = Field(default=None, description="Duration in milliseconds")
    error: str | None = Field(default=None, description="Error message")
    node_executions: list[NodeExecutionResponse] = Field(
        default_factory=list, description="Node execution details"
    )


class ExecutionLogsResponse(BaseModel):
    """Response for execution logs."""

    execution_id: str = Field(..., description="Execution ID")
    logs: list[NodeExecutionResponse] = Field(..., description="Node execution logs")
    total: int = Field(..., description="Total number of log entries")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Items per page")


class ExecutionStats(BaseModel):
    """Execution statistics."""

    total_executions: int = Field(..., description="Total number of executions")
    success_count: int = Field(..., description="Number of successful executions")
    failed_count: int = Field(..., description="Number of failed executions")
    cancelled_count: int = Field(..., description="Number of cancelled executions")
    running_count: int = Field(..., description="Number of running executions")
    pending_count: int = Field(..., description="Number of pending executions")
    success_rate: float = Field(..., description="Success rate (0-1)")
    avg_duration_ms: float | None = Field(
        default=None, description="Average duration in milliseconds"
    )
    executions_by_workflow: dict[str, int] = Field(
        default_factory=dict, description="Execution count by workflow"
    )


class ExecutionCancelResponse(BaseModel):
    """Response for cancelling an execution."""

    id: str = Field(..., description="Execution ID")
    status: str = Field(..., description="New status after cancellation")
    message: str = Field(..., description="Cancellation message")


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str = Field(..., description="Message type (log, status, error, heartbeat)")
    execution_id: str = Field(..., description="Execution ID")
    timestamp: datetime = Field(..., description="Message timestamp")
    data: dict[str, Any] = Field(default_factory=dict, description="Message data")

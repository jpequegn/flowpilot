"""Workflow API schemas for FlowPilot."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    """Schema for creating a workflow."""

    name: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9-]*$",
        description="Workflow name (lowercase, alphanumeric, hyphens)",
    )
    content: str = Field(..., description="Workflow YAML content")


class WorkflowUpdate(BaseModel):
    """Schema for updating a workflow."""

    content: str = Field(..., description="Updated workflow YAML content")


class WorkflowListItem(BaseModel):
    """Summary of a workflow for list responses."""

    name: str = Field(..., description="Workflow name")
    description: str = Field(default="", description="Workflow description")
    version: int = Field(default=1, description="Workflow version")
    path: str = Field(..., description="File path to workflow")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")


class WorkflowDetail(BaseModel):
    """Detailed workflow information."""

    name: str = Field(..., description="Workflow name")
    description: str = Field(default="", description="Workflow description")
    version: int = Field(default=1, description="Workflow version")
    path: str = Field(..., description="File path to workflow")
    content: str = Field(..., description="Raw YAML content")
    triggers: list[dict[str, Any]] = Field(default_factory=list, description="Workflow triggers")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Input definitions")
    node_count: int = Field(default=0, description="Number of nodes")
    created_at: datetime | None = Field(default=None, description="Creation timestamp")
    updated_at: datetime | None = Field(default=None, description="Last update timestamp")


class WorkflowValidation(BaseModel):
    """Validation result for a workflow."""

    valid: bool = Field(..., description="Whether the workflow is valid")
    errors: list[dict[str, Any]] = Field(default_factory=list, description="Validation errors")
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class WorkflowRunRequest(BaseModel):
    """Request to run a workflow."""

    inputs: dict[str, Any] = Field(default_factory=dict, description="Input parameters")


class WorkflowRunResponse(BaseModel):
    """Response from running a workflow."""

    execution_id: str = Field(..., description="Execution ID")
    workflow: str = Field(..., description="Workflow name")
    status: str = Field(..., description="Execution status")

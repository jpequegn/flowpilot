"""Common API schemas for FlowPilot."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str = Field(..., description="Error message")
    errors: list[dict[str, Any]] | None = Field(
        default=None, description="Detailed validation errors"
    )


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str = Field(..., description="Response message")


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T] = Field(..., description="List of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    has_more: bool = Field(..., description="Whether there are more items")

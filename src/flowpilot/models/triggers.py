"""Trigger models for FlowPilot workflows."""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class CronTrigger(BaseModel):
    """Trigger workflow on a cron schedule."""

    type: Literal["cron"]
    schedule: str = Field(..., description="Cron expression (5 or 6 fields)")
    timezone: str = Field(default="local", description="Timezone for schedule")

    @field_validator("schedule")
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        """Validate cron expression format."""
        parts = v.split()
        if len(parts) not in (5, 6):
            msg = f"Cron expression must have 5 or 6 fields, got {len(parts)}"
            raise ValueError(msg)
        return v


class IntervalTrigger(BaseModel):
    """Trigger workflow at regular intervals."""

    type: Literal["interval"]
    every: str = Field(..., description="Interval like '30s', '5m', '2h', '1d'")

    @field_validator("every")
    @classmethod
    def validate_interval(cls, v: str) -> str:
        """Validate interval format."""
        pattern = r"^(\d+)(s|m|h|d)$"
        if not re.match(pattern, v):
            msg = f"Invalid interval format: {v}. Use format like '30s', '5m', '2h', '1d'"
            raise ValueError(msg)
        return v

    def to_seconds(self) -> int:
        """Convert interval to seconds."""
        match = re.match(r"^(\d+)(s|m|h|d)$", self.every)
        if not match:
            msg = f"Invalid interval: {self.every}"
            raise ValueError(msg)

        value = int(match.group(1))
        unit = match.group(2)

        multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        return value * multipliers[unit]


class FileWatchTrigger(BaseModel):
    """Trigger workflow when files change."""

    type: Literal["file-watch"]
    path: str = Field(..., description="Path to watch (file or directory)")
    events: list[Literal["created", "modified", "deleted"]] = Field(
        default=["created"], description="Events to watch for"
    )
    pattern: str | None = Field(default=None, description="Glob pattern to filter files")


class WebhookTrigger(BaseModel):
    """Trigger workflow via HTTP webhook."""

    type: Literal["webhook"]
    path: str = Field(..., description="Webhook path like '/hooks/my-trigger'")
    secret: str | None = Field(default=None, description="Secret for authentication")

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        """Ensure path starts with /."""
        if not v.startswith("/"):
            return f"/{v}"
        return v


class ManualTrigger(BaseModel):
    """Trigger workflow manually."""

    type: Literal["manual"]


# Union type for all triggers
Trigger = Annotated[
    CronTrigger | IntervalTrigger | FileWatchTrigger | WebhookTrigger | ManualTrigger,
    Field(discriminator="type"),
]

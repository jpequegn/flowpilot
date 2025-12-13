"""SQLAlchemy database models for FlowPilot storage layer."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    type_annotation_map: ClassVar[dict[type, type]] = {
        dict[str, Any]: JSON,
    }


class ExecutionStatus(str, enum.Enum):
    """Status of a workflow execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Execution(Base):
    """Record of a workflow execution."""

    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus), default=ExecutionStatus.PENDING
    )
    trigger_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship to node executions
    node_executions: Mapped[list[NodeExecution]] = relationship(
        "NodeExecution",
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Execution(id={self.id!r}, workflow={self.workflow_name!r}, status={self.status})>"


class NodeExecution(Base):
    """Record of a single node execution within a workflow execution."""

    __tablename__ = "node_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("executions.id", ondelete="CASCADE"), index=True
    )
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str] = mapped_column(Text, default="")
    stderr: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")  # JSON string for structured output
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationship to parent execution
    execution: Mapped[Execution] = relationship("Execution", back_populates="node_executions")

    def __repr__(self) -> str:
        return f"<NodeExecution(id={self.id}, node_id={self.node_id!r}, status={self.status!r})>"


class Schedule(Base):
    """Record of a scheduled workflow."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    workflow_path: Mapped[str] = mapped_column(String(500), nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, default=1)  # SQLite boolean
    trigger_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    next_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_run: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    def __repr__(self) -> str:
        return f"<Schedule(id={self.id}, workflow={self.workflow_name!r}, enabled={bool(self.enabled)})>"

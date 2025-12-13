"""Repository classes for FlowPilot storage operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from .models import Execution, ExecutionStatus, NodeExecution, Schedule

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ExecutionRepository:
    """Repository for Execution records."""

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self._session = session

    def create(self, execution: Execution) -> Execution:
        """Create a new execution record.

        Args:
            execution: The execution to create.

        Returns:
            The created execution with any generated values.
        """
        self._session.add(execution)
        self._session.flush()
        return execution

    def update(self, execution: Execution) -> Execution:
        """Update an existing execution record.

        Args:
            execution: The execution to update (must be attached to session).

        Returns:
            The updated execution.
        """
        self._session.flush()
        return execution

    def get_by_id(self, execution_id: str) -> Execution | None:
        """Get an execution by its ID.

        Args:
            execution_id: The UUID of the execution.

        Returns:
            The execution if found, None otherwise.
        """
        stmt = select(Execution).where(Execution.id == execution_id)
        return self._session.scalar(stmt)

    def get_by_workflow(
        self,
        workflow_name: str,
        limit: int = 50,
        status: ExecutionStatus | None = None,
    ) -> list[Execution]:
        """Get executions for a specific workflow.

        Args:
            workflow_name: The name of the workflow.
            limit: Maximum number of executions to return.
            status: Optional status filter.

        Returns:
            List of executions, ordered by start time descending.
        """
        stmt = (
            select(Execution)
            .where(Execution.workflow_name == workflow_name)
            .order_by(Execution.started_at.desc())
            .limit(limit)
        )

        if status is not None:
            stmt = stmt.where(Execution.status == status)

        return list(self._session.scalars(stmt))

    def get_recent(self, limit: int = 50) -> list[Execution]:
        """Get the most recent executions across all workflows.

        Args:
            limit: Maximum number of executions to return.

        Returns:
            List of executions, ordered by start time descending.
        """
        stmt = select(Execution).order_by(Execution.started_at.desc()).limit(limit)
        return list(self._session.scalars(stmt))

    def cleanup_old(self, days: int = 30) -> int:
        """Delete executions older than a specified number of days.

        Args:
            days: Number of days to keep. Executions older than this are deleted.

        Returns:
            Number of executions deleted.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        # Get count first
        stmt = select(Execution).where(Execution.started_at < cutoff)
        old_executions = list(self._session.scalars(stmt))
        count = len(old_executions)

        # Delete (cascades to node_executions)
        for execution in old_executions:
            self._session.delete(execution)

        self._session.flush()
        return count

    def delete(self, execution_id: str) -> bool:
        """Delete an execution by ID.

        Args:
            execution_id: The UUID of the execution to delete.

        Returns:
            True if deleted, False if not found.
        """
        execution = self.get_by_id(execution_id)
        if execution is None:
            return False

        self._session.delete(execution)
        self._session.flush()
        return True


class NodeExecutionRepository:
    """Repository for NodeExecution records."""

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self._session = session

    def create(self, node_execution: NodeExecution) -> NodeExecution:
        """Create a new node execution record.

        Args:
            node_execution: The node execution to create.

        Returns:
            The created node execution.
        """
        self._session.add(node_execution)
        self._session.flush()
        return node_execution

    def create_batch(self, node_executions: list[NodeExecution]) -> list[NodeExecution]:
        """Create multiple node execution records.

        Args:
            node_executions: List of node executions to create.

        Returns:
            The created node executions.
        """
        self._session.add_all(node_executions)
        self._session.flush()
        return node_executions

    def get_by_execution(self, execution_id: str) -> list[NodeExecution]:
        """Get all node executions for a workflow execution.

        Args:
            execution_id: The UUID of the parent execution.

        Returns:
            List of node executions, ordered by start time.
        """
        stmt = (
            select(NodeExecution)
            .where(NodeExecution.execution_id == execution_id)
            .order_by(NodeExecution.started_at.asc().nullsfirst())
        )
        return list(self._session.scalars(stmt))


class ScheduleRepository:
    """Repository for Schedule records."""

    def __init__(self, session: Session) -> None:
        """Initialize the repository.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self._session = session

    def create(self, schedule: Schedule) -> Schedule:
        """Create a new schedule record.

        Args:
            schedule: The schedule to create.

        Returns:
            The created schedule.
        """
        self._session.add(schedule)
        self._session.flush()
        return schedule

    def update(self, schedule: Schedule) -> Schedule:
        """Update an existing schedule record.

        Args:
            schedule: The schedule to update (must be attached to session).

        Returns:
            The updated schedule.
        """
        self._session.flush()
        return schedule

    def get_by_workflow(self, workflow_name: str) -> Schedule | None:
        """Get schedule for a specific workflow.

        Args:
            workflow_name: The name of the workflow.

        Returns:
            The schedule if found, None otherwise.
        """
        stmt = select(Schedule).where(Schedule.workflow_name == workflow_name)
        return self._session.scalar(stmt)

    def get_enabled(self) -> list[Schedule]:
        """Get all enabled schedules.

        Returns:
            List of enabled schedules.
        """
        stmt = select(Schedule).where(Schedule.enabled == 1)
        return list(self._session.scalars(stmt))

    def get_all(self) -> list[Schedule]:
        """Get all schedules.

        Returns:
            List of all schedules.
        """
        stmt = select(Schedule).order_by(Schedule.workflow_name)
        return list(self._session.scalars(stmt))

    def delete(self, workflow_name: str) -> bool:
        """Delete a schedule by workflow name.

        Args:
            workflow_name: The name of the workflow.

        Returns:
            True if deleted, False if not found.
        """
        schedule = self.get_by_workflow(workflow_name)
        if schedule is None:
            return False

        self._session.delete(schedule)
        self._session.flush()
        return True

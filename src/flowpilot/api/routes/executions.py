"""Execution API routes for FlowPilot.

Provides endpoints for listing, querying, and managing workflow executions,
including WebSocket support for live log streaming.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from flowpilot.api.schemas.executions import (
    ExecutionCancelResponse,
    ExecutionDetail,
    ExecutionListItem,
    ExecutionLogsResponse,
    ExecutionStats,
    NodeExecutionResponse,
    WebSocketMessage,
)
from flowpilot.storage.database import Database
from flowpilot.storage.models import Execution, ExecutionStatus, NodeExecution
from flowpilot.storage.repositories import ExecutionRepository, NodeExecutionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/executions", tags=["executions"])

# Global database reference (set via set_database)
_db: Database | None = None


def set_database(db: Database | None) -> None:
    """Set the database instance for execution routes.

    Args:
        db: Database instance to use.
    """
    global _db
    _db = db


def get_database() -> Database:
    """Get the database instance.

    Returns:
        The database instance.

    Raises:
        HTTPException: If database is not configured.
    """
    if _db is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured",
        )
    return _db


class ConnectionManager:
    """Manages WebSocket connections for live log streaming."""

    def __init__(self) -> None:
        """Initialize the connection manager."""
        # Maps execution_id -> list of connected websockets
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, execution_id: str) -> None:
        """Accept and register a WebSocket connection.

        Args:
            websocket: The WebSocket to connect.
            execution_id: The execution ID to subscribe to.
        """
        await websocket.accept()
        async with self._lock:
            if execution_id not in self._connections:
                self._connections[execution_id] = []
            self._connections[execution_id].append(websocket)
        logger.info(f"WebSocket connected for execution {execution_id[:8]}...")

    async def disconnect(self, websocket: WebSocket, execution_id: str) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket to disconnect.
            execution_id: The execution ID it was subscribed to.
        """
        async with self._lock:
            if execution_id in self._connections:
                with contextlib.suppress(ValueError):
                    self._connections[execution_id].remove(websocket)
                if not self._connections[execution_id]:
                    del self._connections[execution_id]
        logger.info(f"WebSocket disconnected for execution {execution_id[:8]}...")

    async def broadcast(self, execution_id: str, message: WebSocketMessage) -> None:
        """Send a message to all connections for an execution.

        Args:
            execution_id: The execution ID to broadcast to.
            message: The message to send.
        """
        async with self._lock:
            connections = self._connections.get(execution_id, []).copy()

        for websocket in connections:
            try:
                await websocket.send_json(message.model_dump(mode="json"))
            except Exception as e:
                logger.warning(f"Failed to send to WebSocket: {e}")
                await self.disconnect(websocket, execution_id)

    async def send_heartbeat(self, execution_id: str) -> None:
        """Send a heartbeat to all connections for an execution.

        Args:
            execution_id: The execution ID to send heartbeat to.
        """
        message = WebSocketMessage(
            type="heartbeat",
            execution_id=execution_id,
            timestamp=datetime.now(),
            data={},
        )
        await self.broadcast(execution_id, message)


# Global connection manager
connection_manager = ConnectionManager()


def _execution_to_list_item(execution: Execution) -> ExecutionListItem:
    """Convert an Execution model to ExecutionListItem schema.

    Args:
        execution: The execution model.

    Returns:
        ExecutionListItem schema.
    """
    return ExecutionListItem(
        id=execution.id,
        workflow_name=execution.workflow_name,
        status=execution.status.value,
        trigger_type=execution.trigger_type,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        duration_ms=execution.duration_ms,
    )


def _node_execution_to_response(node: NodeExecution) -> NodeExecutionResponse:
    """Convert a NodeExecution model to response schema.

    Args:
        node: The node execution model.

    Returns:
        NodeExecutionResponse schema.
    """
    return NodeExecutionResponse(
        id=node.id,
        node_id=node.node_id,
        node_type=node.node_type,
        status=node.status,
        started_at=node.started_at,
        finished_at=node.finished_at,
        duration_ms=node.duration_ms,
        stdout=node.stdout,
        stderr=node.stderr,
        output=node.output,
        error=node.error,
    )


def _execution_to_detail(
    execution: Execution, node_executions: list[NodeExecution]
) -> ExecutionDetail:
    """Convert an Execution model to ExecutionDetail schema.

    Args:
        execution: The execution model.
        node_executions: List of node execution models.

    Returns:
        ExecutionDetail schema.
    """
    return ExecutionDetail(
        id=execution.id,
        workflow_name=execution.workflow_name,
        workflow_path=execution.workflow_path,
        status=execution.status.value,
        trigger_type=execution.trigger_type,
        inputs=execution.inputs,
        started_at=execution.started_at,
        finished_at=execution.finished_at,
        duration_ms=execution.duration_ms,
        error=execution.error,
        node_executions=[_node_execution_to_response(n) for n in node_executions],
    )


@router.get("", response_model=list[ExecutionListItem])
def list_executions(
    workflow: str | None = Query(None, description="Filter by workflow name"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> list[ExecutionListItem]:
    """List workflow executions with optional filtering.

    Args:
        workflow: Optional workflow name filter.
        status: Optional status filter (pending, running, success, failed, cancelled).
        limit: Maximum number of results (1-200, default 50).
        offset: Pagination offset.

    Returns:
        List of execution summaries.
    """
    db = get_database()

    with db.session_scope() as session:
        stmt = select(Execution).order_by(Execution.started_at.desc())

        if workflow:
            stmt = stmt.where(Execution.workflow_name == workflow)

        if status:
            try:
                status_enum = ExecutionStatus(status)
                stmt = stmt.where(Execution.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status: {status}. Must be one of: "
                    f"{', '.join(s.value for s in ExecutionStatus)}",
                ) from None

        stmt = stmt.offset(offset).limit(limit)
        executions = list(session.scalars(stmt))

        return [_execution_to_list_item(e) for e in executions]


@router.get("/stats", response_model=ExecutionStats)
def get_execution_stats(
    workflow: str | None = Query(None, description="Filter by workflow name"),
) -> ExecutionStats:
    """Get execution statistics.

    Args:
        workflow: Optional workflow name filter.

    Returns:
        Execution statistics.
    """
    db = get_database()

    with db.session_scope() as session:
        base_query = select(Execution)
        if workflow:
            base_query = base_query.where(Execution.workflow_name == workflow)

        # Get all executions for counting
        executions = list(session.scalars(base_query))

        total = len(executions)
        if total == 0:
            return ExecutionStats(
                total_executions=0,
                success_count=0,
                failed_count=0,
                cancelled_count=0,
                running_count=0,
                pending_count=0,
                success_rate=0.0,
                avg_duration_ms=None,
                executions_by_workflow={},
            )

        # Count by status
        success_count = sum(1 for e in executions if e.status == ExecutionStatus.SUCCESS)
        failed_count = sum(1 for e in executions if e.status == ExecutionStatus.FAILED)
        cancelled_count = sum(1 for e in executions if e.status == ExecutionStatus.CANCELLED)
        running_count = sum(1 for e in executions if e.status == ExecutionStatus.RUNNING)
        pending_count = sum(1 for e in executions if e.status == ExecutionStatus.PENDING)

        # Calculate success rate (exclude pending/running)
        completed = success_count + failed_count + cancelled_count
        success_rate = success_count / completed if completed > 0 else 0.0

        # Calculate average duration (only completed executions)
        durations = [e.duration_ms for e in executions if e.duration_ms is not None]
        avg_duration = sum(durations) / len(durations) if durations else None

        # Count by workflow
        workflow_counts: dict[str, int] = {}
        for e in executions:
            workflow_counts[e.workflow_name] = workflow_counts.get(e.workflow_name, 0) + 1

        return ExecutionStats(
            total_executions=total,
            success_count=success_count,
            failed_count=failed_count,
            cancelled_count=cancelled_count,
            running_count=running_count,
            pending_count=pending_count,
            success_rate=success_rate,
            avg_duration_ms=avg_duration,
            executions_by_workflow=workflow_counts,
        )


@router.get("/{execution_id}", response_model=ExecutionDetail)
def get_execution(execution_id: str) -> ExecutionDetail:
    """Get detailed information about an execution.

    Args:
        execution_id: The execution ID.

    Returns:
        Detailed execution information including node executions.

    Raises:
        HTTPException: If execution not found.
    """
    db = get_database()

    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        execution = repo.get_by_id(execution_id)

        if execution is None:
            raise HTTPException(
                status_code=404,
                detail=f"Execution not found: {execution_id}",
            )

        node_repo = NodeExecutionRepository(session)
        node_executions = node_repo.get_by_execution(execution_id)

        return _execution_to_detail(execution, node_executions)


@router.delete("/{execution_id}", response_model=ExecutionCancelResponse)
def cancel_execution(execution_id: str) -> ExecutionCancelResponse:
    """Cancel a running or pending execution.

    Args:
        execution_id: The execution ID to cancel.

    Returns:
        Cancellation response.

    Raises:
        HTTPException: If execution not found or cannot be cancelled.
    """
    db = get_database()

    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        execution = repo.get_by_id(execution_id)

        if execution is None:
            raise HTTPException(
                status_code=404,
                detail=f"Execution not found: {execution_id}",
            )

        if execution.status not in (ExecutionStatus.PENDING, ExecutionStatus.RUNNING):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel execution with status: {execution.status.value}",
            )

        # Update status to cancelled
        execution.status = ExecutionStatus.CANCELLED
        execution.finished_at = datetime.now()
        repo.update(execution)

        return ExecutionCancelResponse(
            id=execution_id,
            status=ExecutionStatus.CANCELLED.value,
            message="Execution cancelled successfully",
        )


@router.get("/{execution_id}/logs", response_model=ExecutionLogsResponse)
def get_execution_logs(
    execution_id: str,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
) -> ExecutionLogsResponse:
    """Get paginated execution logs (node executions).

    Args:
        execution_id: The execution ID.
        page: Page number (1-indexed).
        page_size: Number of items per page (1-200).

    Returns:
        Paginated execution logs.

    Raises:
        HTTPException: If execution not found.
    """
    db = get_database()

    with db.session_scope() as session:
        # Verify execution exists
        repo = ExecutionRepository(session)
        execution = repo.get_by_id(execution_id)

        if execution is None:
            raise HTTPException(
                status_code=404,
                detail=f"Execution not found: {execution_id}",
            )

        # Get all node executions for this execution
        node_repo = NodeExecutionRepository(session)
        all_nodes = node_repo.get_by_execution(execution_id)

        total = len(all_nodes)
        start = (page - 1) * page_size
        end = start + page_size
        page_nodes = all_nodes[start:end]

        return ExecutionLogsResponse(
            execution_id=execution_id,
            logs=[_node_execution_to_response(n) for n in page_nodes],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.websocket("/{execution_id}/ws")
async def websocket_logs(websocket: WebSocket, execution_id: str) -> None:
    """WebSocket endpoint for live execution logs.

    Streams execution status updates and node execution logs in real-time.

    Args:
        websocket: The WebSocket connection.
        execution_id: The execution ID to stream logs for.
    """
    db = get_database()

    # Verify execution exists
    with db.session_scope() as session:
        repo = ExecutionRepository(session)
        execution = repo.get_by_id(execution_id)

        if execution is None:
            await websocket.close(code=4004, reason="Execution not found")
            return

    await connection_manager.connect(websocket, execution_id)

    try:
        # Send initial status
        initial_message = WebSocketMessage(
            type="status",
            execution_id=execution_id,
            timestamp=datetime.now(),
            data={"status": "connected", "message": "Streaming logs..."},
        )
        await websocket.send_json(initial_message.model_dump(mode="json"))

        # Keep connection alive and send heartbeats
        last_log_count = 0
        while True:
            try:
                # Check for client messages (ping/pong)
                # Use timeout to allow periodic status checks
                try:
                    data = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                    if data == "ping":
                        await websocket.send_text("pong")
                except TimeoutError:
                    pass

                # Check execution status and send updates
                with db.session_scope() as session:
                    repo = ExecutionRepository(session)
                    execution = repo.get_by_id(execution_id)

                    if execution is None:
                        break

                    # Check for new node executions
                    node_repo = NodeExecutionRepository(session)
                    nodes = node_repo.get_by_execution(execution_id)

                    # Send any new node logs
                    if len(nodes) > last_log_count:
                        for node in nodes[last_log_count:]:
                            log_message = WebSocketMessage(
                                type="log",
                                execution_id=execution_id,
                                timestamp=datetime.now(),
                                data={
                                    "node_id": node.node_id,
                                    "node_type": node.node_type,
                                    "status": node.status,
                                    "stdout": node.stdout,
                                    "stderr": node.stderr,
                                    "error": node.error,
                                },
                            )
                            await websocket.send_json(log_message.model_dump(mode="json"))
                        last_log_count = len(nodes)

                    # Check if execution is complete
                    if execution.status in (
                        ExecutionStatus.SUCCESS,
                        ExecutionStatus.FAILED,
                        ExecutionStatus.CANCELLED,
                    ):
                        final_message = WebSocketMessage(
                            type="status",
                            execution_id=execution_id,
                            timestamp=datetime.now(),
                            data={
                                "status": execution.status.value,
                                "finished_at": execution.finished_at.isoformat()
                                if execution.finished_at
                                else None,
                                "duration_ms": execution.duration_ms,
                                "error": execution.error,
                            },
                        )
                        await websocket.send_json(final_message.model_dump(mode="json"))
                        break

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                error_message = WebSocketMessage(
                    type="error",
                    execution_id=execution_id,
                    timestamp=datetime.now(),
                    data={"error": str(e)},
                )
                with contextlib.suppress(Exception):
                    await websocket.send_json(error_message.model_dump(mode="json"))
                break

    finally:
        await connection_manager.disconnect(websocket, execution_id)


# Utility function for other modules to broadcast updates
async def broadcast_execution_update(
    execution_id: str,
    update_type: str,
    data: dict[str, Any],
) -> None:
    """Broadcast an execution update to all connected WebSocket clients.

    This can be called from the workflow runner to push real-time updates.

    Args:
        execution_id: The execution ID.
        update_type: Type of update (log, status, error).
        data: Update data.
    """
    message = WebSocketMessage(
        type=update_type,
        execution_id=execution_id,
        timestamp=datetime.now(),
        data=data,
    )
    await connection_manager.broadcast(execution_id, message)

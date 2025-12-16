"""Shared dependencies for FlowPilot API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, HTTPException, Request

if TYPE_CHECKING:
    from flowpilot.engine.runner import WorkflowRunner


def get_workflows_dir(request: Request) -> Path:
    """Get the workflows directory from app state.

    Args:
        request: FastAPI request object.

    Returns:
        Path to workflows directory.
    """
    workflows_dir: Path = request.app.state.workflows_dir
    return workflows_dir


def get_runner(request: Request) -> WorkflowRunner | None:
    """Get the workflow runner from app state.

    Args:
        request: FastAPI request object.

    Returns:
        WorkflowRunner instance or None.
    """
    from flowpilot.engine.runner import WorkflowRunner as Runner

    runner: Runner | None = request.app.state.runner
    return runner


def require_runner(request: Request) -> WorkflowRunner:
    """Get the workflow runner, raising if not configured.

    Args:
        request: FastAPI request object.

    Returns:
        WorkflowRunner instance.

    Raises:
        HTTPException: If runner is not configured.
    """
    from flowpilot.engine.runner import WorkflowRunner as Runner

    runner: Runner | None = request.app.state.runner
    if runner is None:
        raise HTTPException(
            status_code=503,
            detail="Workflow runner not configured",
        )
    return runner


# Type aliases for dependency injection
WorkflowsDir = Annotated[Path, Depends(get_workflows_dir)]
OptionalRunner = Annotated["WorkflowRunner | None", Depends(get_runner)]
RequiredRunner = Annotated["WorkflowRunner", Depends(require_runner)]

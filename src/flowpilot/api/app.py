"""FlowPilot FastAPI application factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import health, workflows
from .webhooks import (
    router as webhook_router,
)
from .webhooks import (
    set_global_webhook_runner,
    set_workflows_dir,
)

if TYPE_CHECKING:
    from flowpilot.engine.runner import WorkflowRunner


def create_app(
    *,
    workflows_dir: Path | None = None,
    runner: WorkflowRunner | None = None,
    enable_cors: bool = True,
    cors_origins: list[str] | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        workflows_dir: Directory containing workflow YAML files.
            Defaults to ~/.flowpilot/workflows.
        runner: WorkflowRunner instance for executing workflows.
        enable_cors: Enable CORS middleware.
        cors_origins: List of allowed CORS origins.
            Defaults to ["*"] for development.

    Returns:
        Configured FastAPI application.
    """
    app = FastAPI(
        title="FlowPilot API",
        description="Workflow automation and orchestration API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Set up workflows directory
    if workflows_dir is None:
        workflows_dir = Path.home() / ".flowpilot" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)

    # Store config in app state
    app.state.workflows_dir = workflows_dir
    app.state.runner = runner

    # Set up webhook service (for serve command compatibility)
    set_workflows_dir(workflows_dir)
    if runner:
        set_global_webhook_runner(runner)

    # Configure CORS
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Register routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(workflows.router, prefix="/api", tags=["workflows"])
    app.include_router(webhook_router, prefix="/api", tags=["webhooks"])

    return app

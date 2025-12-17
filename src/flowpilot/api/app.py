"""FlowPilot FastAPI application factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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


def get_static_dir() -> Path | None:
    """Get the path to the static directory if it exists.

    Returns:
        Path to static directory if it exists, None otherwise.
    """
    # Check for bundled static files in package
    static_dir = Path(__file__).parent.parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        return static_dir
    return None


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
        version="1.0.0",
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

    # Register API routers
    app.include_router(health.router, prefix="/api", tags=["health"])
    app.include_router(workflows.router, prefix="/api", tags=["workflows"])
    app.include_router(webhook_router, prefix="/api", tags=["webhooks"])

    # Serve frontend static files if available
    static_dir = get_static_dir()
    if static_dir:
        # Mount static assets (JS, CSS, images)
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # Serve index.html for all non-API routes (SPA support)
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> FileResponse:
            """Serve the SPA frontend for all non-API routes."""
            # Don't serve for API routes
            if full_path.startswith("api/"):
                from fastapi import HTTPException

                raise HTTPException(status_code=404, detail="Not found")

            # Check if the file exists in static directory
            file_path = static_dir / full_path
            if file_path.is_file():
                return FileResponse(file_path)

            # Otherwise serve index.html for SPA routing
            return FileResponse(static_dir / "index.html")

    return app

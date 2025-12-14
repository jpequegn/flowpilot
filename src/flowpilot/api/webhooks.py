"""Webhook service for FlowPilot workflows.

Provides HTTP webhook endpoints that trigger workflow execution when called.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

if TYPE_CHECKING:
    from flowpilot.engine.runner import WorkflowRunner
    from flowpilot.models.triggers import WebhookTrigger

logger = logging.getLogger(__name__)

# FastAPI router for webhook endpoints
router = APIRouter(prefix="/hooks", tags=["webhooks"])

# Registry of active webhooks: path -> WebhookConfig
_webhooks: dict[str, dict[str, Any]] = {}

# Global runner reference (set via set_global_webhook_runner)
_global_runner: WorkflowRunner | None = None

# Default workflows directory
_workflows_dir: Path = Path.home() / ".flowpilot" / "workflows"


def set_global_webhook_runner(runner: WorkflowRunner | None) -> None:
    """Set the global workflow runner for webhook execution.

    Args:
        runner: WorkflowRunner instance to use for executing workflows.
    """
    global _global_runner
    _global_runner = runner


def set_workflows_dir(workflows_dir: Path) -> None:
    """Set the workflows directory.

    Args:
        workflows_dir: Path to the workflows directory.
    """
    global _workflows_dir
    _workflows_dir = workflows_dir


def register_webhook(
    path: str,
    workflow_name: str,
    workflow_path: str,
    secret: str | None = None,
) -> str:
    """Register a webhook endpoint for a workflow.

    Args:
        path: The webhook path (e.g., '/github-push').
        workflow_name: Name of the workflow to trigger.
        workflow_path: Path to the workflow YAML file.
        secret: Optional secret for authentication.

    Returns:
        Webhook identifier.
    """
    # Normalize path to ensure it starts with /
    if not path.startswith("/"):
        path = "/" + path

    # Resolve secret from environment variable if needed
    resolved_secret = _resolve_secret(secret)

    _webhooks[path] = {
        "workflow_name": workflow_name,
        "workflow_path": workflow_path,
        "secret": resolved_secret,
    }

    logger.info(
        f"Registered webhook for workflow '{workflow_name}' at path '{path}' "
        f"(auth={'enabled' if resolved_secret else 'disabled'})"
    )

    return f"webhook:{workflow_name}:{path}"


def unregister_webhook(workflow_name: str) -> bool:
    """Remove all webhooks for a workflow.

    Args:
        workflow_name: Name of the workflow.

    Returns:
        True if any webhooks were removed, False otherwise.
    """
    to_remove = [
        path
        for path, config in _webhooks.items()
        if config["workflow_name"] == workflow_name
    ]

    for path in to_remove:
        del _webhooks[path]
        logger.info(f"Unregistered webhook at path '{path}'")

    return len(to_remove) > 0


def get_webhooks() -> list[dict[str, Any]]:
    """List all registered webhooks.

    Returns:
        List of webhook configurations.
    """
    return [
        {
            "path": path,
            "workflow_name": config["workflow_name"],
            "has_secret": config["secret"] is not None,
        }
        for path, config in _webhooks.items()
    ]


def get_webhook(workflow_name: str) -> dict[str, Any] | None:
    """Get webhook info for a specific workflow.

    Args:
        workflow_name: Name of the workflow.

    Returns:
        Webhook information or None if not found.
    """
    for path, config in _webhooks.items():
        if config["workflow_name"] == workflow_name:
            return {
                "path": path,
                "workflow_name": config["workflow_name"],
                "has_secret": config["secret"] is not None,
            }
    return None


def _resolve_secret(secret: str | None) -> str | None:
    """Resolve secret from environment variable if needed.

    Args:
        secret: Secret string, possibly in ${VAR} format.

    Returns:
        Resolved secret value or None.
    """
    if not secret:
        return None

    # Check for ${VAR} format
    if secret.startswith("${") and secret.endswith("}"):
        env_var = secret[2:-1]
        return os.environ.get(env_var)

    return secret


def _verify_signature(body: bytes, secret: str, signature: str) -> bool:
    """Verify HMAC signature (GitHub style).

    Args:
        body: Request body bytes.
        secret: The secret key.
        signature: The signature header value.

    Returns:
        True if signature is valid.
    """
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    # Handle both 'sha256=xxx' and plain 'xxx' formats
    if signature.startswith("sha256="):
        signature = signature[7:]

    return hmac.compare_digest(expected, signature)


@router.post("/{path:path}")
async def handle_webhook(
    path: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    """Handle incoming webhook requests.

    Args:
        path: The webhook path.
        request: The FastAPI request object.
        background_tasks: FastAPI background tasks.
        x_webhook_secret: Simple secret header.
        x_hub_signature_256: GitHub-style HMAC signature header.

    Returns:
        Response with execution ID and status.

    Raises:
        HTTPException: If webhook not found or authentication fails.
    """
    full_path = "/" + path

    if full_path not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    config = _webhooks[full_path]

    # Read request body
    body = await request.body()

    # Verify authentication if secret is configured
    if config["secret"]:
        if x_webhook_secret:
            # Simple secret comparison
            if x_webhook_secret != config["secret"]:
                logger.warning(f"Invalid webhook secret for path '{full_path}'")
                raise HTTPException(status_code=401, detail="Invalid secret")
        elif x_hub_signature_256:
            # HMAC signature verification (GitHub style)
            if not _verify_signature(body, config["secret"], x_hub_signature_256):
                logger.warning(f"Invalid webhook signature for path '{full_path}'")
                raise HTTPException(status_code=401, detail="Invalid signature")
        else:
            logger.warning(f"Missing authentication for webhook path '{full_path}'")
            raise HTTPException(status_code=401, detail="Authentication required")

    # Parse request body as JSON
    try:
        body_json = await request.json()
    except Exception:
        body_json = {}

    # Build workflow inputs from request
    client_host = request.client.host if request.client else "unknown"
    inputs = {
        "_webhook": {
            "path": full_path,
            "method": request.method,
            "headers": dict(request.headers),
            "query": dict(request.query_params),
            "body": body_json,
            "client_ip": client_host,
            "timestamp": datetime.now().isoformat(),
        }
    }

    # Generate execution ID
    execution_id = str(uuid.uuid4())

    # Execute workflow in background
    background_tasks.add_task(
        _execute_webhook_workflow,
        workflow_name=config["workflow_name"],
        workflow_path=config["workflow_path"],
        inputs=inputs,
        execution_id=execution_id,
    )

    logger.info(
        f"Webhook triggered workflow '{config['workflow_name']}' "
        f"(execution_id={execution_id[:8]}...)"
    )

    return {
        "status": "accepted",
        "execution_id": execution_id,
        "workflow": config["workflow_name"],
    }


def _execute_webhook_workflow(
    workflow_name: str,
    workflow_path: str,
    inputs: dict[str, Any],
    execution_id: str,
) -> None:
    """Execute a workflow triggered by a webhook.

    This runs in a background task.

    Args:
        workflow_name: Name of the workflow.
        workflow_path: Path to the workflow file.
        inputs: Input data including webhook request info.
        execution_id: The execution ID.
    """
    from flowpilot.engine.parser import WorkflowParser

    if _global_runner is None:
        logger.error(f"Cannot execute workflow '{workflow_name}': no runner configured")
        return

    path = Path(workflow_path)
    if not path.exists():
        logger.error(f"Workflow file not found: {path}")
        return

    try:
        parser = WorkflowParser()
        workflow = parser.parse_file(path)

        logger.info(f"Executing webhook workflow '{workflow_name}' (id={execution_id[:8]}...)")

        # Run the async workflow
        asyncio.run(
            _global_runner.run(
                workflow,
                inputs=inputs,
                execution_id=execution_id,
                workflow_path=str(path),
                trigger_type="webhook",
            )
        )

        logger.info(f"Completed webhook workflow '{workflow_name}' (id={execution_id[:8]}...)")

    except Exception as e:
        logger.exception(f"Failed to execute webhook workflow '{workflow_name}': {e}")


class WebhookService:
    """Service class for managing webhooks.

    Provides a cleaner interface for the ScheduleManager to interact with.
    """

    def __init__(self, workflows_dir: Path | None = None) -> None:
        """Initialize the webhook service.

        Args:
            workflows_dir: Directory containing workflow files.
        """
        if workflows_dir:
            set_workflows_dir(workflows_dir)

    def register(
        self,
        workflow_name: str,
        trigger: WebhookTrigger,
        workflow_path: str,
    ) -> str:
        """Register a webhook for a workflow.

        Args:
            workflow_name: Name of the workflow.
            trigger: Webhook trigger configuration.
            workflow_path: Path to the workflow file.

        Returns:
            Webhook identifier.
        """
        return register_webhook(
            path=trigger.path,
            workflow_name=workflow_name,
            workflow_path=workflow_path,
            secret=trigger.secret,
        )

    def unregister(self, workflow_name: str) -> bool:
        """Unregister webhooks for a workflow.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            True if removed, False if not found.
        """
        return unregister_webhook(workflow_name)

    def get_webhooks(self) -> list[dict[str, Any]]:
        """Get all registered webhooks.

        Returns:
            List of webhook configurations.
        """
        return get_webhooks()

    def get_webhook(self, workflow_name: str) -> dict[str, Any] | None:
        """Get webhook info for a specific workflow.

        Args:
            workflow_name: Name of the workflow.

        Returns:
            Webhook information or None.
        """
        return get_webhook(workflow_name)

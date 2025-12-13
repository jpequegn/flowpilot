"""Webhook endpoint handling for FlowPilot workflows."""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

if TYPE_CHECKING:
    from flowpilot.engine.runner import WorkflowRunner

logger = logging.getLogger(__name__)

# Router for webhook endpoints
router = APIRouter(prefix="/hooks", tags=["webhooks"])

# Registry of active webhooks: path -> {workflow_name, workflow_path, secret}
_webhooks: dict[str, dict[str, Any]] = {}

# Global reference to runner for webhook execution
_global_runner: WorkflowRunner | None = None


def set_global_webhook_runner(runner: WorkflowRunner | None) -> None:
    """Set the global workflow runner for webhook execution.

    Args:
        runner: WorkflowRunner instance to use for executing workflows.
    """
    global _global_runner
    _global_runner = runner


def register_webhook(
    path: str,
    workflow_name: str,
    workflow_path: str,
    secret: str | None = None,
) -> str:
    """Register a webhook endpoint.

    Args:
        path: Webhook path (e.g., /github-push).
        workflow_name: Name of the workflow to trigger.
        workflow_path: Path to the workflow file.
        secret: Optional secret for authentication.

    Returns:
        The registered webhook path.
    """
    # Normalize path
    if not path.startswith("/"):
        path = "/" + path

    _webhooks[path] = {
        "workflow_name": workflow_name,
        "workflow_path": workflow_path,
        "secret": secret,
    }

    logger.info(f"Registered webhook for workflow '{workflow_name}' at path: {path}")
    return path


def unregister_webhook(workflow_name: str) -> bool:
    """Remove webhook for a workflow.

    Args:
        workflow_name: Name of the workflow to unregister.

    Returns:
        True if webhook was removed, False if not found.
    """
    to_remove = [
        path for path, config in _webhooks.items() if config["workflow_name"] == workflow_name
    ]

    if not to_remove:
        return False

    for path in to_remove:
        del _webhooks[path]
        logger.info(f"Unregistered webhook at path: {path}")

    return True


def get_webhooks() -> list[dict[str, Any]]:
    """List all registered webhooks.

    Returns:
        List of webhook information dictionaries.
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


def _verify_secret(
    config: dict[str, Any],
    body: bytes,
    x_webhook_secret: str | None,
    x_signature: str | None,
) -> bool:
    """Verify webhook secret/signature.

    Args:
        config: Webhook configuration with secret.
        body: Request body bytes.
        x_webhook_secret: Simple secret header value.
        x_signature: HMAC signature header value.

    Returns:
        True if verification passes, False otherwise.

    Raises:
        HTTPException: If authentication is required but missing/invalid.
    """
    secret = config.get("secret")
    if not secret:
        return True

    if x_webhook_secret:
        # Simple secret comparison
        if x_webhook_secret != secret:
            raise HTTPException(status_code=401, detail="Invalid secret")
        return True

    if x_signature:
        # HMAC signature verification (GitHub style)
        expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        expected_header = f"sha256={expected}"
        if not hmac.compare_digest(expected_header, x_signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        return True

    # Secret required but not provided
    raise HTTPException(status_code=401, detail="Authentication required")


@router.post("/{path:path}")
async def handle_webhook(
    path: str,
    request: Request,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    x_signature: str | None = Header(None, alias="X-Hub-Signature-256"),
) -> dict[str, Any]:
    """Handle incoming webhook requests.

    Args:
        path: The webhook path.
        request: The incoming request.
        background_tasks: FastAPI background tasks.
        x_webhook_secret: Simple secret header.
        x_signature: HMAC signature header (GitHub style).

    Returns:
        Dictionary with execution status and ID.
    """
    full_path = "/" + path

    if full_path not in _webhooks:
        raise HTTPException(status_code=404, detail="Webhook not found")

    config = _webhooks[full_path]

    # Get request body for verification
    body = await request.body()

    # Verify secret/signature if configured
    _verify_secret(config, body, x_webhook_secret, x_signature)

    # Parse request body
    try:
        body_json = (await request.json()) if body else {}
    except Exception:
        body_json = {}

    # Build workflow inputs from request
    inputs = {
        "_webhook": {
            "path": full_path,
            "method": request.method,
            "headers": dict(request.headers),
            "query": dict(request.query_params),
            "body": body_json,
            "client_ip": request.client.host if request.client else None,
            "timestamp": datetime.now().isoformat(),
        }
    }

    # Generate execution ID
    execution_id = str(uuid.uuid4())

    # Execute workflow in background
    background_tasks.add_task(
        _execute_webhook_workflow,
        config["workflow_name"],
        config["workflow_path"],
        inputs,
        execution_id,
    )

    logger.info(
        f"Webhook triggered workflow '{config['workflow_name']}' (execution_id={execution_id})"
    )

    return {
        "status": "accepted",
        "execution_id": execution_id,
        "workflow": config["workflow_name"],
    }


async def _execute_webhook_workflow(
    workflow_name: str,
    workflow_path: str,
    inputs: dict[str, Any],
    execution_id: str,
) -> None:
    """Execute a workflow triggered by a webhook.

    Args:
        workflow_name: Name of the workflow.
        workflow_path: Path to the workflow file.
        inputs: Workflow inputs including webhook data.
        execution_id: Execution identifier.
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

        logger.info(f"Executing webhook workflow: {workflow_name}")

        await _global_runner.run(
            workflow,
            inputs=inputs,
            workflow_path=str(path),
            trigger_type="webhook",
        )

        logger.info(f"Completed webhook workflow: {workflow_name}")

    except Exception as e:
        logger.exception(f"Failed to execute webhook workflow '{workflow_name}': {e}")

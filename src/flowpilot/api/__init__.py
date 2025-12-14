"""FlowPilot API server.

Provides FastAPI-based HTTP API for workflow management, webhooks,
and real-time execution monitoring.
"""

from .webhooks import (
    WebhookService,
    get_webhook,
    get_webhooks,
    register_webhook,
    router as webhook_router,
    set_global_webhook_runner,
    set_workflows_dir,
    unregister_webhook,
)

__all__ = [
    "WebhookService",
    "get_webhook",
    "get_webhooks",
    "register_webhook",
    "set_global_webhook_runner",
    "set_workflows_dir",
    "unregister_webhook",
    "webhook_router",
]

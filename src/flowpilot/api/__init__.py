"""FlowPilot API server.

Provides FastAPI-based HTTP API for workflow management, webhooks,
and real-time execution monitoring.
"""

from .app import create_app
from .webhooks import (
    WebhookService,
    get_webhook,
    get_webhooks,
    register_webhook,
    set_global_webhook_runner,
    set_workflows_dir,
    unregister_webhook,
)
from .webhooks import (
    router as webhook_router,
)

__all__ = [
    "WebhookService",
    "create_app",
    "get_webhook",
    "get_webhooks",
    "register_webhook",
    "set_global_webhook_runner",
    "set_workflows_dir",
    "unregister_webhook",
    "webhook_router",
]

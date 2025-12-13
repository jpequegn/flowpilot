"""FlowPilot API server.

This module provides the FastAPI-based API server for FlowPilot,
including webhook endpoints for triggering workflows via HTTP.
"""

from .webhooks import (
    get_webhook,
    get_webhooks,
    register_webhook,
    router,
    set_global_webhook_runner,
    unregister_webhook,
)

__all__ = [
    "get_webhook",
    "get_webhooks",
    "register_webhook",
    "router",
    "set_global_webhook_runner",
    "unregister_webhook",
]

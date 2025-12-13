"""CLI commands for FlowPilot."""

# Import command modules to register them with the app
# These imports have side effects (register commands via @app.command())
from flowpilot.cli.commands import (
    history,
    init,
    list_cmd,
    logs,
    run,
    schedule,
    validate,
)

__all__ = ["history", "init", "list_cmd", "logs", "run", "schedule", "validate"]

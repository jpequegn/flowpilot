"""Init command for FlowPilot CLI."""

import typer
import yaml

from flowpilot.cli import (
    CONFIG_FILE,
    FLOWPILOT_DIR,
    LOGS_DIR,
    WORKFLOWS_DIR,
    app,
    console,
)

EXAMPLE_WORKFLOW = """\
name: hello-world
description: Example workflow to get started with FlowPilot

triggers:
  - type: manual

nodes:
  - id: greet
    type: shell
    command: echo "Hello from FlowPilot!"

  - id: show-date
    type: shell
    command: date
    depends_on:
      - greet
"""


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
) -> None:
    """Initialize FlowPilot directory structure.

    Creates the ~/.flowpilot directory with:
    - workflows/ directory for workflow YAML files
    - logs/ directory for execution logs
    - config.yaml with default settings
    - An example hello-world workflow
    """
    if FLOWPILOT_DIR.exists() and not force:
        console.print(f"[yellow]FlowPilot already initialized at {FLOWPILOT_DIR}[/]")
        console.print("Use [cyan]--force[/] to reinitialize")
        raise typer.Exit(1)

    # Create directories
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    # Create default config
    default_config = {
        "server": {
            "host": "127.0.0.1",
            "port": 8080,
        },
        "claude": {
            "default_model": "sonnet",
        },
        "execution": {
            "default_timeout": 300,
            "max_parallel_nodes": 10,
        },
    }
    CONFIG_FILE.write_text(yaml.dump(default_config, default_flow_style=False, sort_keys=False))

    # Create example workflow
    example_path = WORKFLOWS_DIR / "hello-world.yaml"
    example_path.write_text(EXAMPLE_WORKFLOW)

    console.print(f"[green]✓[/] Initialized FlowPilot at {FLOWPILOT_DIR}")
    console.print(f"[green]✓[/] Created config file: {CONFIG_FILE}")
    console.print("[green]✓[/] Created example workflow: hello-world")
    console.print()
    console.print("Run [cyan]flowpilot run hello-world[/] to test your setup")

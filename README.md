# FlowPilot

A workflow automation tool for macOS with Claude Code integration.

## Features

- **YAML-first workflows** - Define workflows as code, version control friendly
- **Visual preview** - See your workflow as a flow diagram
- **Claude Code integration** - Native support for Claude CLI and API
- **Flexible triggers** - Cron, file watching, webhooks, manual
- **Logic nodes** - Conditions, loops, parallel execution
- **Web UI** - Modern interface for managing workflows

## Installation

```bash
pip install flowpilot
```

## Quick Start

```bash
# Initialize FlowPilot
flowpilot init

# Start the server
flowpilot serve

# Open http://localhost:8080
```

## Creating a Workflow

Create `~/.flowpilot/workflows/hello.yaml`:

```yaml
name: hello-world
description: A simple example workflow

triggers:
  - type: manual

nodes:
  - id: greet
    type: shell
    command: echo "Hello from FlowPilot!"

  - id: ai-response
    type: claude-cli
    prompt: "Say hello in a creative way"
```

Run it:

```bash
flowpilot run hello-world
```

## Documentation

See [docs/plans/2025-12-12-flowpilot-design.md](docs/plans/2025-12-12-flowpilot-design.md) for the full design document.

## License

MIT

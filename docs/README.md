# FlowPilot Documentation

FlowPilot is a workflow automation tool for macOS with Claude Code integration.

## Quick Navigation

- **[Getting Started](getting-started/)** - Installation and first workflow
- **[Node Types](nodes/)** - Reference for all available nodes
- **[CLI Reference](cli/)** - Command-line interface documentation
- **[API Reference](api/)** - REST API endpoints
- **[Examples](examples/)** - Example workflows to get you started
- **[Guides](guides/)** - In-depth guides and tutorials

## What is FlowPilot?

FlowPilot is a YAML-based workflow automation tool designed for developers. It allows you to:

- Define workflows as code in simple YAML files
- Execute shell commands, HTTP requests, file operations
- Use conditions, loops, and parallel execution
- Integrate with Claude CLI for AI-powered automation
- Monitor workflow execution through a web UI
- Schedule workflows with triggers (manual, cron, file-watch)

## Key Features

- **YAML-based workflows** - Human-readable, version-controllable
- **Rich node types** - Shell, HTTP, file I/O, conditions, loops, parallel
- **Claude integration** - AI-powered nodes via Claude CLI or API
- **Templating** - Jinja2-style expressions with access to context
- **Web UI** - Real-time monitoring and workflow visualization
- **Triggers** - Manual, cron schedules, file watchers

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FlowPilot                         │
├─────────────────────────────────────────────────────┤
│  CLI (click)           │  Web UI (React)            │
├────────────────────────┼────────────────────────────┤
│            FastAPI REST + WebSocket API             │
├─────────────────────────────────────────────────────┤
│  Workflow Engine       │  Scheduler                 │
│  - YAML Parser         │  - Cron Triggers           │
│  - DAG Executor        │  - File Watchers           │
│  - Node Handlers       │  - Manual Triggers         │
├─────────────────────────────────────────────────────┤
│                   SQLite Storage                    │
└─────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Install FlowPilot
pip install flowpilot-*.whl

# Initialize a project
flowpilot init

# Create a workflow
cat > workflows/hello.yaml << EOF
name: hello-world
triggers:
  - type: manual
nodes:
  - id: greet
    type: shell
    config:
      command: echo "Hello from FlowPilot!"
EOF

# Run the workflow
flowpilot run hello

# Or start the server with web UI
flowpilot serve
```

## Requirements

- macOS (primary platform)
- Python 3.11+
- Node.js/Bun (for frontend development)
- Claude CLI (optional, for AI nodes)

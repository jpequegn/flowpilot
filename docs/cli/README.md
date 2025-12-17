# CLI Reference

FlowPilot provides a command-line interface for managing and running workflows.

## Installation

After installing FlowPilot, the `flowpilot` command is available:

```bash
flowpilot --help
```

## Commands Overview

| Command | Description |
|---------|-------------|
| `flowpilot init` | Initialize a new FlowPilot project |
| `flowpilot serve` | Start the server with web UI |
| `flowpilot run` | Execute a workflow |
| `flowpilot --version` | Show version information |
| `flowpilot --help` | Show help message |

## Global Options

```
--version  Show version and exit
--help     Show help message and exit
```

---

## flowpilot init

Initialize a new FlowPilot project in the current directory.

### Usage

```bash
flowpilot init [OPTIONS]
```

### Options

```
--workflows PATH  Path for workflows directory (default: ./workflows)
--db PATH         Path for SQLite database (default: ./flowpilot.db)
--help            Show help message
```

### Examples

```bash
# Initialize with defaults
flowpilot init

# Custom paths
flowpilot init --workflows ./my-workflows --db ./data/flowpilot.db
```

### What it Creates

```
./
├── flowpilot.db        # SQLite database
└── workflows/          # Workflow directory
    └── example.yaml    # Example workflow
```

---

## flowpilot serve

Start the FlowPilot server with REST API and web UI.

### Usage

```bash
flowpilot serve [OPTIONS]
```

### Options

```
--host TEXT       Host to bind to (default: 127.0.0.1)
--port INTEGER    Port to bind to (default: 8080)
--workflows PATH  Path to workflows directory (default: ./workflows)
--db PATH         Path to SQLite database (default: ./flowpilot.db)
--reload          Enable auto-reload for development
--help            Show help message
```

### Examples

```bash
# Start with defaults
flowpilot serve

# Custom host and port
flowpilot serve --host 0.0.0.0 --port 9000

# Development mode with auto-reload
flowpilot serve --reload

# Custom paths
flowpilot serve --workflows ~/my-workflows --db ~/data/flowpilot.db
```

### What it Provides

- **REST API** at `http://localhost:8080/api/`
- **Web UI** at `http://localhost:8080/`
- **WebSocket** for real-time updates

---

## flowpilot run

Execute a workflow.

### Usage

```bash
flowpilot run [OPTIONS] WORKFLOW
```

### Arguments

```
WORKFLOW  Workflow name or path to YAML file (required)
```

### Options

```
--input JSON   Input data as JSON string
--sync         Run synchronously and wait for completion
--verbose      Show detailed output
--help         Show help message
```

### Examples

```bash
# Run by workflow name
flowpilot run example

# Run by file path
flowpilot run workflows/backup.yaml

# With input data
flowpilot run data-pipeline --input '{"date": "2024-01-15"}'

# Synchronous execution with verbose output
flowpilot run backup --sync --verbose
```

### Output

```
Running workflow: example-workflow
Execution ID: abc123
Status: completed
Duration: 1.5s
```

With `--verbose`:

```
Running workflow: example-workflow
Execution ID: abc123

Executing node: step1
  Command: echo "Hello"
  Output: Hello
  Status: completed (120ms)

Executing node: step2
  Command: echo "World"
  Output: World
  Status: completed (95ms)

Workflow completed successfully
Total duration: 215ms
```

---

## Environment Variables

FlowPilot respects these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `FLOWPILOT_HOST` | Server host | `127.0.0.1` |
| `FLOWPILOT_PORT` | Server port | `8080` |
| `FLOWPILOT_WORKFLOWS_DIR` | Workflows directory | `./workflows` |
| `FLOWPILOT_DB_PATH` | Database path | `./flowpilot.db` |
| `FLOWPILOT_LOG_LEVEL` | Logging level | `INFO` |
| `ANTHROPIC_API_KEY` | For claude_api nodes | - |

### Example

```bash
export FLOWPILOT_PORT=9000
export FLOWPILOT_LOG_LEVEL=DEBUG
flowpilot serve
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

---

## Tips

### Running as a Service

Use a process manager like `launchd` on macOS:

```xml
<!-- ~/Library/LaunchAgents/com.flowpilot.server.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.flowpilot.server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/flowpilot</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/path/to/project</string>
</dict>
</plist>
```

Load with:
```bash
launchctl load ~/Library/LaunchAgents/com.flowpilot.server.plist
```

### Shell Completion

Generate shell completions (if supported):

```bash
# Bash
flowpilot --install-completion bash

# Zsh
flowpilot --install-completion zsh
```

---

## See Also

- [Configuration](../getting-started/configuration.md)
- [API Reference](../api/)
- [Quick Start](../getting-started/quick-start.md)

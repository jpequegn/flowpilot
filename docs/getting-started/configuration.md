# Configuration

FlowPilot can be configured through command-line arguments, environment variables, and configuration files.

## Command-Line Configuration

### Server Configuration

```bash
flowpilot serve [OPTIONS]

Options:
  --host TEXT       Host to bind to (default: 127.0.0.1)
  --port INTEGER    Port to bind to (default: 8080)
  --workflows PATH  Path to workflows directory (default: ./workflows)
  --db PATH         Path to SQLite database (default: ./flowpilot.db)
  --reload          Enable auto-reload for development
```

### Run Configuration

```bash
flowpilot run [OPTIONS] WORKFLOW

Arguments:
  WORKFLOW  Workflow name or path to YAML file

Options:
  --input JSON    Input data as JSON string
  --sync          Run synchronously and wait for completion
  --verbose       Show detailed output
```

## Environment Variables

FlowPilot respects the following environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `FLOWPILOT_HOST` | Server host | `127.0.0.1` |
| `FLOWPILOT_PORT` | Server port | `8080` |
| `FLOWPILOT_WORKFLOWS_DIR` | Workflows directory | `./workflows` |
| `FLOWPILOT_DB_PATH` | Database path | `./flowpilot.db` |
| `FLOWPILOT_LOG_LEVEL` | Logging level | `INFO` |
| `ANTHROPIC_API_KEY` | API key for claude_api nodes | - |

Example:

```bash
export FLOWPILOT_PORT=9000
export FLOWPILOT_LOG_LEVEL=DEBUG
flowpilot serve
```

## Directory Structure

A typical FlowPilot project structure:

```
my-project/
├── flowpilot.db          # Execution history database
├── workflows/            # Workflow definitions
│   ├── daily-backup.yaml
│   ├── api-monitor.yaml
│   └── data-pipeline/
│       ├── extract.yaml
│       └── transform.yaml
└── logs/                 # Optional: execution logs
```

## Workflow Discovery

FlowPilot discovers workflows by:

1. Scanning the workflows directory recursively
2. Finding all `.yaml` and `.yml` files
3. Parsing files with valid workflow structure

Workflows can be run by:
- **Name**: The `name` field in the YAML file
- **Path**: Relative or absolute path to the file

```bash
# By name
flowpilot run daily-backup

# By path
flowpilot run workflows/daily-backup.yaml
flowpilot run ~/other-project/workflow.yaml
```

## Database Configuration

FlowPilot uses SQLite for storing:
- Execution history
- Workflow metadata
- Node results and logs

The database is created automatically on first run. To use a different location:

```bash
flowpilot serve --db /path/to/flowpilot.db
```

### Database Maintenance

```bash
# View database location
ls -la flowpilot.db

# Backup the database
cp flowpilot.db flowpilot.db.backup

# The database can be safely deleted to reset history
rm flowpilot.db
```

## Logging

Configure logging verbosity:

```bash
# Set log level via environment
export FLOWPILOT_LOG_LEVEL=DEBUG

# Or use verbose flag
flowpilot run workflow --verbose
```

Log levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Security Considerations

### Shell Commands

Shell nodes execute commands directly on your system. Be careful with:
- User-provided input in templates
- Commands that modify system files
- Workflows from untrusted sources

### API Keys

For `claude_api` nodes, set your API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Never commit API keys to version control.

### Network Access

The server binds to localhost by default. To expose externally:

```bash
# Bind to all interfaces (use with caution)
flowpilot serve --host 0.0.0.0
```

Consider using a reverse proxy (nginx, caddy) for production deployments.

## Next Steps

- [Quick Start](quick-start.md) - Create your first workflow
- [CLI Reference](../cli/) - Complete CLI documentation
- [API Reference](../api/) - REST API documentation

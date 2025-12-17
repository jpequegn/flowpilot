# Triggers

Triggers define when and how workflows are executed.

## Trigger Types

| Type | Description |
|------|-------------|
| `manual` | Run on demand via CLI or UI |
| `cron` | Run on a schedule |
| `file-watch` | Run when files change |

## Manual Trigger

The simplest trigger - runs when explicitly invoked.

```yaml
triggers:
  - type: manual
```

**Invocation:**
```bash
# CLI
flowpilot run workflow-name

# API
curl -X POST http://localhost:8080/api/workflows/workflow-name/run
```

---

## Cron Trigger

Run workflows on a schedule using cron syntax.

```yaml
triggers:
  - type: cron
    schedule: "0 9 * * *"  # Daily at 9 AM
```

### Cron Syntax

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, Sunday=0)
│ │ │ │ │
* * * * *
```

### Common Schedules

| Schedule | Cron Expression | Description |
|----------|-----------------|-------------|
| Every minute | `* * * * *` | Run every minute |
| Every hour | `0 * * * *` | Run at the start of every hour |
| Daily at midnight | `0 0 * * *` | Run at 00:00 every day |
| Daily at 9 AM | `0 9 * * *` | Run at 09:00 every day |
| Weekdays at 9 AM | `0 9 * * 1-5` | Run at 09:00 Monday-Friday |
| Every Monday | `0 0 * * 1` | Run at midnight on Mondays |
| First of month | `0 0 1 * *` | Run at midnight on the 1st |
| Every 15 minutes | `*/15 * * * *` | Run every 15 minutes |
| Every 6 hours | `0 */6 * * *` | Run every 6 hours |

### Examples

**Daily report at 8 AM:**
```yaml
triggers:
  - type: cron
    schedule: "0 8 * * *"
```

**Weekly cleanup on Sunday at 2 AM:**
```yaml
triggers:
  - type: cron
    schedule: "0 2 * * 0"
```

**Business hours check (every hour, 9-5, Mon-Fri):**
```yaml
triggers:
  - type: cron
    schedule: "0 9-17 * * 1-5"
```

**Multiple schedules:**
```yaml
triggers:
  - type: cron
    schedule: "0 9 * * 1-5"   # Weekdays at 9 AM
  - type: cron
    schedule: "0 12 * * 1-5"  # Weekdays at noon
```

---

## File Watch Trigger

Run workflows when files are created, modified, or deleted.

```yaml
triggers:
  - type: file-watch
    path: ~/Downloads
    events:
      - created
    pattern: "*.pdf"
```

### Configuration

| Property | Description | Default |
|----------|-------------|---------|
| `path` | Directory to watch | Required |
| `events` | Event types to trigger on | `[created, modified]` |
| `pattern` | Glob pattern to match | `*` (all files) |
| `recursive` | Watch subdirectories | `true` |
| `debounce` | Seconds to wait before triggering | `1.0` |

### Event Types

- `created` - New file created
- `modified` - File content changed
- `deleted` - File removed
- `moved` - File renamed or moved

### Examples

**Process new CSV files:**
```yaml
triggers:
  - type: file-watch
    path: ~/data/incoming
    events:
      - created
    pattern: "*.csv"
```

**Monitor config changes:**
```yaml
triggers:
  - type: file-watch
    path: /etc/myapp
    events:
      - modified
    pattern: "*.yaml"
    recursive: false
```

**Watch for any file changes:**
```yaml
triggers:
  - type: file-watch
    path: ~/Documents/notes
    events:
      - created
      - modified
      - deleted
```

### Accessing File Information

When triggered by file watch, the file path is available in input:

```yaml
- id: process-file
  type: shell
  config:
    command: "process-file '{{ input.file_path }}'"
```

---

## Multiple Triggers

Workflows can have multiple triggers:

```yaml
triggers:
  # Run on schedule
  - type: cron
    schedule: "0 9 * * *"

  # Also run manually
  - type: manual

  # Also run on file changes
  - type: file-watch
    path: ~/data
    events:
      - created
```

---

## Trigger Context

Each trigger provides context to the workflow:

### Manual Trigger
```yaml
input:
  trigger_type: "manual"
  triggered_at: "2024-01-15T10:30:00Z"
  # Plus any input provided
```

### Cron Trigger
```yaml
input:
  trigger_type: "cron"
  triggered_at: "2024-01-15T09:00:00Z"
  schedule: "0 9 * * *"
```

### File Watch Trigger
```yaml
input:
  trigger_type: "file-watch"
  triggered_at: "2024-01-15T10:30:00Z"
  file_path: "/Users/me/Downloads/report.pdf"
  event_type: "created"
```

---

## Best Practices

### Scheduling

1. **Avoid peak times** - Don't schedule resource-intensive workflows during busy hours
2. **Stagger schedules** - Don't run all workflows at the same time
3. **Consider timezones** - Cron uses the server's timezone

### File Watching

1. **Be specific with patterns** - Avoid watching too many files
2. **Use debouncing** - Prevent rapid re-triggers
3. **Handle race conditions** - Files may still be writing when triggered

### General

1. **Always include manual trigger** - For testing and debugging
2. **Log trigger information** - Helps with debugging
3. **Handle failures** - Add error notification

---

## Example: Complete Trigger Setup

```yaml
name: data-pipeline
description: Process incoming data files

triggers:
  # Process new files immediately
  - type: file-watch
    path: ~/data/incoming
    events:
      - created
    pattern: "*.json"
    debounce: 2.0

  # Daily summary at 6 PM
  - type: cron
    schedule: "0 18 * * *"

  # Manual trigger for testing
  - type: manual

nodes:
  - id: log-trigger
    type: log
    config:
      message: "Triggered by {{ input.trigger_type }} at {{ input.triggered_at }}"
      level: info

  - id: process
    type: condition
    config:
      expression: "{{ input.trigger_type == 'file-watch' }}"
      then_branch: process-file
      else_branch: process-batch
    depends_on:
      - log-trigger

  - id: process-file
    type: shell
    config:
      command: "./process-single.sh '{{ input.file_path }}'"

  - id: process-batch
    type: shell
    config:
      command: "./process-batch.sh"
```

---

## See Also

- [Workflow Syntax](workflow-syntax.md) - Complete YAML reference
- [CLI Reference](../cli/) - Running workflows
- [Examples](../examples/) - Trigger usage examples

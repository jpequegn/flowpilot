# Log Node

Output messages to the workflow execution log.

## Configuration

```yaml
- id: my-log
  type: log
  config:
    message: string       # Required: message to log
    level: string         # Optional: log level (default: info)
```

### Log Levels

- `debug` - Detailed debugging information
- `info` - General information (default)
- `warning` - Warning messages
- `error` - Error messages

## Examples

### Basic Logging

```yaml
- id: log-start
  type: log
  config:
    message: "Workflow started"
    level: info
```

### With Template Variables

```yaml
- id: log-user
  type: log
  config:
    message: "Processing request for user: {{ input.user_id }}"
    level: info
```

### Logging Node Results

```yaml
- id: fetch-data
  type: http
  config:
    url: https://api.example.com/data

- id: log-result
  type: log
  config:
    message: "Fetched {{ nodes.fetch-data.output.body.items | length }} items"
    level: info
  depends_on:
    - fetch-data
```

### Debug Logging

```yaml
- id: debug-input
  type: log
  config:
    message: "Input received: {{ input | tojson }}"
    level: debug

- id: process
  type: shell
  config:
    command: ./process.sh
  depends_on:
    - debug-input

- id: debug-output
  type: log
  config:
    message: "Process output: {{ nodes.process.output.stdout }}"
    level: debug
  depends_on:
    - process
```

### Warning Messages

```yaml
- id: check-disk
  type: shell
  config:
    command: df -h / | awk 'NR==2 {print $5}' | tr -d '%'

- id: warn-low-disk
  type: log
  config:
    message: "Warning: Disk usage is {{ nodes.check-disk.output.stdout }}%"
    level: warning
  condition: "{{ nodes.check-disk.output.stdout | int > 80 }}"
  depends_on:
    - check-disk
```

### Error Logging

```yaml
- id: api-call
  type: http
  config:
    url: https://api.example.com/data

- id: log-error
  type: log
  config:
    message: "API call failed with status {{ nodes.api-call.output.status_code }}"
    level: error
  condition: "{{ nodes.api-call.output.status_code != 200 }}"
  depends_on:
    - api-call
```

### Structured Logging

```yaml
- id: structured-log
  type: log
  config:
    message: |
      {
        "event": "processing_complete",
        "items_processed": {{ nodes.process.output.count }},
        "duration_ms": {{ nodes.process.output.duration_ms }},
        "timestamp": "{{ now() }}"
      }
    level: info
```

### Progress Tracking

```yaml
- id: step-1
  type: shell
  config:
    command: ./step1.sh

- id: log-step-1
  type: log
  config:
    message: "✓ Step 1 completed"
    level: info
  depends_on:
    - step-1

- id: step-2
  type: shell
  config:
    command: ./step2.sh
  depends_on:
    - step-1

- id: log-step-2
  type: log
  config:
    message: "✓ Step 2 completed"
    level: info
  depends_on:
    - step-2

- id: step-3
  type: shell
  config:
    command: ./step3.sh
  depends_on:
    - step-2

- id: log-complete
  type: log
  config:
    message: "✓ All steps completed successfully"
    level: info
  depends_on:
    - step-3
```

## Output

The log node outputs:

```json
{
  "message": "Workflow started",
  "level": "info",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Viewing Logs

Logs appear in:
- CLI output when running with `--verbose`
- Web UI execution details
- Execution history API endpoint

## Best Practices

1. **Use appropriate levels** - Reserve `error` for actual errors
2. **Include context** - Log relevant IDs and values
3. **Be concise** - Avoid overly verbose messages
4. **Use structured format** for complex data
5. **Log at boundaries** - Start, end, and error points
6. **Don't log secrets** - Mask sensitive data

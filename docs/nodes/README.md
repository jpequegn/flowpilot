# Node Types

Nodes are the building blocks of FlowPilot workflows. Each node performs a specific operation.

## Available Node Types

| Type | Description | Category |
|------|-------------|----------|
| [shell](shell.md) | Execute shell commands | Execution |
| [http](http.md) | Make HTTP requests | Execution |
| [file_read](file.md) | Read file contents | File I/O |
| [file_write](file.md) | Write content to files | File I/O |
| [condition](condition.md) | Conditional branching | Control Flow |
| [loop](loop.md) | Iterate over items | Control Flow |
| [parallel](parallel.md) | Execute branches in parallel | Control Flow |
| [delay](delay.md) | Pause execution | Control Flow |
| [log](log.md) | Output log messages | Utility |
| [claude_cli](claude.md) | AI via Claude CLI | AI |
| [claude_api](claude.md) | AI via Anthropic API | AI |

## Common Node Structure

All nodes share a common structure:

```yaml
- id: unique-node-id        # Required: unique identifier
  type: node-type           # Required: one of the types above
  config:                   # Required: type-specific configuration
    key: value
  depends_on:               # Optional: list of node IDs
    - previous-node
  condition: "{{ expr }}"   # Optional: skip if evaluates to false
  retry:                    # Optional: retry configuration
    max_attempts: 3
    delay_seconds: 5
```

## Node Execution

Nodes execute based on their dependencies:

```yaml
nodes:
  - id: first
    type: shell
    config:
      command: echo "First"

  - id: second
    type: shell
    config:
      command: echo "Second"
    depends_on:
      - first  # Waits for 'first' to complete

  - id: parallel-a
    type: shell
    config:
      command: echo "Parallel A"
    depends_on:
      - second

  - id: parallel-b
    type: shell
    config:
      command: echo "Parallel B"
    depends_on:
      - second
    # parallel-a and parallel-b run concurrently
```

## Accessing Node Results

Each node's result is available to subsequent nodes via templating:

```yaml
- id: fetch-data
  type: http
  config:
    url: https://api.example.com/data
    method: GET

- id: process-data
  type: shell
  config:
    command: echo "Status: {{ nodes.fetch-data.output.status_code }}"
  depends_on:
    - fetch-data
```

## Error Handling

### Retry Configuration

```yaml
- id: flaky-request
  type: http
  config:
    url: https://api.example.com/data
  retry:
    max_attempts: 3
    delay_seconds: 5
    backoff_multiplier: 2  # Exponential backoff
```

### Conditional Execution

```yaml
- id: fallback
  type: shell
  config:
    command: echo "Using fallback"
  condition: "{{ nodes.primary.status == 'failed' }}"
```

## Next Steps

- Explore individual node documentation
- See [Examples](../examples/) for real-world usage
- Learn about [Templating](../guides/templating.md) for dynamic values

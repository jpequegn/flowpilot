# Workflow Syntax

Complete reference for FlowPilot workflow YAML structure.

## Basic Structure

```yaml
name: workflow-name          # Required: unique identifier
description: Description     # Optional: human-readable description

triggers:                    # Required: at least one trigger
  - type: manual

nodes:                       # Required: list of nodes
  - id: node-id
    type: node-type
    config:
      # type-specific configuration
```

## Workflow Properties

### name (required)

Unique identifier for the workflow. Used in CLI commands and API calls.

```yaml
name: my-workflow
```

**Rules:**
- Must be unique within the workflows directory
- Use lowercase with hyphens
- No spaces or special characters

### description (optional)

Human-readable description of what the workflow does.

```yaml
description: |
  This workflow performs daily backups
  of important directories.
```

### triggers (required)

List of trigger configurations. At least one trigger is required.

```yaml
triggers:
  - type: manual
  - type: cron
    schedule: "0 9 * * *"
```

See [Triggers Guide](triggers.md) for details.

### nodes (required)

List of node definitions. Nodes execute based on dependencies.

```yaml
nodes:
  - id: step-1
    type: shell
    config:
      command: echo "First"

  - id: step-2
    type: shell
    config:
      command: echo "Second"
    depends_on:
      - step-1
```

---

## Node Structure

### id (required)

Unique identifier within the workflow.

```yaml
- id: my-node
```

**Rules:**
- Must be unique within the workflow
- Use lowercase with hyphens
- Referenced by other nodes in `depends_on`

### type (required)

The node type determines what operation is performed.

```yaml
- id: example
  type: shell  # or: http, file_read, file_write, condition, loop, parallel, delay, log, claude_cli, claude_api
```

### config (required)

Type-specific configuration object.

```yaml
- id: example
  type: shell
  config:
    command: echo "Hello"
    timeout: 30
```

### depends_on (optional)

List of node IDs that must complete before this node runs.

```yaml
- id: step-2
  type: shell
  config:
    command: echo "After step-1"
  depends_on:
    - step-1
```

**Execution order:**
- Nodes without dependencies run first
- Nodes with dependencies wait for all dependencies to complete
- Independent nodes can run in parallel

### condition (optional)

Expression that must evaluate to true for the node to execute.

```yaml
- id: conditional-node
  type: shell
  config:
    command: echo "Only if condition is true"
  condition: "{{ input.enabled == true }}"
```

### retry (optional)

Retry configuration for failed nodes.

```yaml
- id: flaky-request
  type: http
  config:
    url: https://api.example.com/data
  retry:
    max_attempts: 3
    delay_seconds: 5
    backoff_multiplier: 2
```

**Properties:**
- `max_attempts` - Maximum retry attempts (default: 1)
- `delay_seconds` - Initial delay between retries
- `backoff_multiplier` - Multiply delay by this factor each retry

---

## Execution Order

Nodes execute based on their dependency graph:

```yaml
nodes:
  # Level 0 - No dependencies, runs first
  - id: fetch-config
    type: file_read
    config:
      path: /etc/config.yaml

  - id: fetch-data
    type: http
    config:
      url: https://api.example.com/data

  # Level 1 - Depends on level 0
  - id: process
    type: shell
    config:
      command: ./process.sh
    depends_on:
      - fetch-config
      - fetch-data

  # Level 2 - Depends on level 1
  - id: save-results
    type: file_write
    config:
      path: /tmp/results.json
      content: "{{ nodes.process.output.stdout }}"
    depends_on:
      - process
```

**Execution flow:**
1. `fetch-config` and `fetch-data` run in parallel
2. `process` runs after both complete
3. `save-results` runs after `process`

---

## Variable Access

### Input Data

Access workflow input via `input`:

```yaml
- id: greet
  type: shell
  config:
    command: echo "Hello {{ input.name }}"
```

Run with input:
```bash
flowpilot run workflow --input '{"name": "World"}'
```

### Environment Variables

Access environment via `env()`:

```yaml
- id: example
  type: shell
  config:
    command: echo "User: {{ env('USER') }}"
```

### Node Results

Access previous node results via `nodes`:

```yaml
- id: use-result
  type: shell
  config:
    command: echo "Status: {{ nodes.api-call.output.status_code }}"
  depends_on:
    - api-call
```

**Available properties:**
- `nodes.<id>.status` - Node status (pending, running, completed, failed)
- `nodes.<id>.output` - Node output data
- `nodes.<id>.duration_ms` - Execution duration
- `nodes.<id>.error` - Error message if failed

---

## Comments

YAML comments are supported:

```yaml
name: example

# This is a comment
nodes:
  - id: step-1
    type: shell
    config:
      command: echo "Hello"  # Inline comment
```

---

## Multi-line Strings

Use YAML block scalars for multi-line content:

### Literal Block (preserves newlines)

```yaml
- id: script
  type: shell
  config:
    command: |
      echo "Line 1"
      echo "Line 2"
      echo "Line 3"
```

### Folded Block (joins lines)

```yaml
- id: description
  type: log
  config:
    message: >
      This is a long message
      that spans multiple lines
      but will be joined.
```

---

## Complete Example

```yaml
name: complete-example
description: Demonstrates all workflow features

triggers:
  - type: manual
  - type: cron
    schedule: "0 9 * * 1-5"

nodes:
  # Extract
  - id: fetch-data
    type: http
    config:
      url: "{{ env('API_URL') }}/data"
      headers:
        Authorization: "Bearer {{ env('API_TOKEN') }}"
    retry:
      max_attempts: 3
      delay_seconds: 5

  # Transform
  - id: process-data
    type: shell
    config:
      command: |
        echo '{{ nodes.fetch-data.output.body | tojson }}' | \
        jq '.items | map(select(.active))'
    depends_on:
      - fetch-data

  # Conditional
  - id: check-results
    type: condition
    config:
      expression: "{{ nodes.process-data.output.stdout | fromjson | length > 0 }}"
      then_branch: save-results
      else_branch: no-results
    depends_on:
      - process-data

  # Load
  - id: save-results
    type: file_write
    config:
      path: "/data/output/{{ now('%Y%m%d') }}.json"
      content: "{{ nodes.process-data.output.stdout }}"
      create_dirs: true

  - id: no-results
    type: log
    config:
      message: "No active items found"
      level: warning

  # Notification
  - id: notify
    type: http
    config:
      url: "{{ env('SLACK_WEBHOOK') }}"
      method: POST
      body:
        text: "Pipeline complete: {{ nodes.process-data.output.stdout | fromjson | length }} items"
    condition: "{{ env('SLACK_WEBHOOK') != '' }}"
    depends_on:
      - save-results
```

---

## See Also

- [Templating](templating.md) - Expression syntax and filters
- [Triggers](triggers.md) - Trigger configuration
- [Node Types](../nodes/) - All available nodes

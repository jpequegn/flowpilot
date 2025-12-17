# Parallel Node

Execute multiple branches concurrently.

## Configuration

```yaml
- id: my-parallel
  type: parallel
  config:
    branches:             # Required: list of branch configurations
      - id: string        # Required: branch identifier
        nodes: array      # Required: nodes to execute in this branch
    wait_for: all|any     # Optional: completion strategy (default: all)
    max_concurrent: int   # Optional: max concurrent branches (default: unlimited)
```

## Examples

### Basic Parallel Execution

```yaml
- id: parallel-tasks
  type: parallel
  config:
    branches:
      - id: branch-a
        nodes:
          - id: task-a
            type: shell
            config:
              command: echo "Task A"

      - id: branch-b
        nodes:
          - id: task-b
            type: shell
            config:
              command: echo "Task B"

      - id: branch-c
        nodes:
          - id: task-c
            type: shell
            config:
              command: echo "Task C"
```

### Parallel API Calls

```yaml
- id: fetch-all-data
  type: parallel
  config:
    branches:
      - id: users
        nodes:
          - id: fetch-users
            type: http
            config:
              url: https://api.example.com/users

      - id: products
        nodes:
          - id: fetch-products
            type: http
            config:
              url: https://api.example.com/products

      - id: orders
        nodes:
          - id: fetch-orders
            type: http
            config:
              url: https://api.example.com/orders
```

### Multi-Step Branches

```yaml
- id: parallel-pipelines
  type: parallel
  config:
    branches:
      - id: data-pipeline
        nodes:
          - id: extract
            type: shell
            config:
              command: ./extract.sh

          - id: transform
            type: shell
            config:
              command: ./transform.sh
            depends_on:
              - extract

      - id: log-pipeline
        nodes:
          - id: collect-logs
            type: shell
            config:
              command: ./collect-logs.sh

          - id: analyze-logs
            type: shell
            config:
              command: ./analyze-logs.sh
            depends_on:
              - collect-logs
```

### Wait for Any (First Success)

```yaml
- id: redundant-fetch
  type: parallel
  config:
    wait_for: any
    branches:
      - id: primary
        nodes:
          - id: fetch-primary
            type: http
            config:
              url: https://primary-api.example.com/data

      - id: backup
        nodes:
          - id: fetch-backup
            type: http
            config:
              url: https://backup-api.example.com/data
```

### Limited Concurrency

```yaml
- id: limited-parallel
  type: parallel
  config:
    max_concurrent: 2  # Only 2 branches at a time
    branches:
      - id: task-1
        nodes:
          - id: heavy-task-1
            type: shell
            config:
              command: ./heavy-process.sh 1

      - id: task-2
        nodes:
          - id: heavy-task-2
            type: shell
            config:
              command: ./heavy-process.sh 2

      - id: task-3
        nodes:
          - id: heavy-task-3
            type: shell
            config:
              command: ./heavy-process.sh 3

      - id: task-4
        nodes:
          - id: heavy-task-4
            type: shell
            config:
              command: ./heavy-process.sh 4
```

### Combining Results

```yaml
- id: fetch-parallel
  type: parallel
  config:
    branches:
      - id: api-a
        nodes:
          - id: fetch-a
            type: http
            config:
              url: https://api-a.example.com/data

      - id: api-b
        nodes:
          - id: fetch-b
            type: http
            config:
              url: https://api-b.example.com/data

- id: combine-results
  type: shell
  config:
    command: |
      echo "Results from A: {{ nodes.fetch-parallel.branches.api-a.fetch-a.output.body | tojson }}"
      echo "Results from B: {{ nodes.fetch-parallel.branches.api-b.fetch-b.output.body | tojson }}"
  depends_on:
    - fetch-parallel
```

## Output

The parallel node outputs:

```json
{
  "branches": {
    "branch-a": {
      "status": "completed",
      "duration_ms": 1500,
      "nodes": {
        "task-a": {
          "status": "completed",
          "output": { "stdout": "Task A" }
        }
      }
    },
    "branch-b": {
      "status": "completed",
      "duration_ms": 1200,
      "nodes": {
        "task-b": {
          "status": "completed",
          "output": { "stdout": "Task B" }
        }
      }
    }
  },
  "completed": 2,
  "failed": 0,
  "duration_ms": 1500
}
```

Access in templates:
- `{{ nodes.my-parallel.branches.branch-a.task-a.output.stdout }}`
- `{{ nodes.my-parallel.output.completed }}`

## Error Handling

### Wait for All (Default)

All branches must complete. If any branch fails, the parallel node reports failure but other branches continue.

### Wait for Any

The parallel node completes when the first branch succeeds. Other branches are cancelled.

### Per-Branch Error Handling

```yaml
- id: resilient-parallel
  type: parallel
  config:
    branches:
      - id: critical
        nodes:
          - id: critical-task
            type: http
            config:
              url: https://critical.example.com/data
            retry:
              max_attempts: 3
              delay_seconds: 2

      - id: optional
        nodes:
          - id: optional-task
            type: http
            config:
              url: https://optional.example.com/data
            # No retry - failure is acceptable
```

## Best Practices

1. **Use for independent operations** - Don't parallelize dependent tasks
2. **Limit concurrency** when resources are constrained
3. **Handle failures** appropriately for each branch
4. **Consider using loop** with `max_parallel` for homogeneous tasks
5. **Monitor execution time** to identify bottlenecks
6. **Name branches descriptively** for easier debugging

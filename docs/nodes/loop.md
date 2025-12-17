# Loop Node

Iterate over a collection and execute nodes for each item.

## Configuration

```yaml
- id: my-loop
  type: loop
  config:
    items: array|string   # Required: array or expression yielding array
    item_var: string      # Optional: variable name for current item (default: item)
    index_var: string     # Optional: variable name for index (default: index)
    body: array           # Required: nodes to execute for each item
    max_parallel: int     # Optional: max parallel iterations (default: 1)
```

## Examples

### Basic Loop

```yaml
- id: process-files
  type: loop
  config:
    items:
      - file1.txt
      - file2.txt
      - file3.txt
    body:
      - id: process
        type: shell
        config:
          command: "cat {{ item }}"
```

### Loop with Index

```yaml
- id: numbered-output
  type: loop
  config:
    items: ["apple", "banana", "cherry"]
    item_var: fruit
    index_var: i
    body:
      - id: print
        type: shell
        config:
          command: "echo '{{ i + 1 }}. {{ fruit }}'"
```

### Loop Over API Response

```yaml
- id: fetch-users
  type: http
  config:
    url: https://api.example.com/users

- id: process-users
  type: loop
  config:
    items: "{{ nodes.fetch-users.output.body.users }}"
    item_var: user
    body:
      - id: notify-user
        type: http
        config:
          url: https://notifications.example.com/send
          method: POST
          body:
            user_id: "{{ user.id }}"
            message: "Hello {{ user.name }}"
  depends_on:
    - fetch-users
```

### Parallel Processing

```yaml
- id: parallel-downloads
  type: loop
  config:
    items:
      - https://example.com/file1.zip
      - https://example.com/file2.zip
      - https://example.com/file3.zip
    item_var: url
    max_parallel: 3
    body:
      - id: download
        type: shell
        config:
          command: "curl -O {{ url }}"
```

### Loop with Multiple Nodes

```yaml
- id: backup-databases
  type: loop
  config:
    items: ["users", "products", "orders"]
    item_var: db
    body:
      - id: dump
        type: shell
        config:
          command: "pg_dump {{ db }} > /backups/{{ db }}.sql"

      - id: compress
        type: shell
        config:
          command: "gzip /backups/{{ db }}.sql"
        depends_on:
          - dump

      - id: log
        type: log
        config:
          message: "Backed up {{ db }}"
        depends_on:
          - compress
```

### Loop with Condition

```yaml
- id: selective-process
  type: loop
  config:
    items: "{{ nodes.fetch-items.output.body.items }}"
    item_var: item
    body:
      - id: check-type
        type: condition
        config:
          expression: "{{ item.type == 'important' }}"
          then_branch: process-important
          else_branch: skip

      - id: process-important
        type: shell
        config:
          command: "./process-important.sh {{ item.id }}"

      - id: skip
        type: log
        config:
          message: "Skipping {{ item.id }}"
```

### Dynamic Item List

```yaml
- id: get-servers
  type: shell
  config:
    command: "cat /etc/servers.json"

- id: health-check
  type: loop
  config:
    items: "{{ nodes.get-servers.output.stdout | fromjson }}"
    item_var: server
    max_parallel: 5
    body:
      - id: ping
        type: http
        config:
          url: "{{ server.url }}/health"
          timeout: 5
  depends_on:
    - get-servers
```

## Output

The loop node outputs:

```json
{
  "iterations": 3,
  "completed": 3,
  "failed": 0,
  "results": [
    { "item": "file1.txt", "status": "completed" },
    { "item": "file2.txt", "status": "completed" },
    { "item": "file3.txt", "status": "completed" }
  ]
}
```

Access in templates:
- `{{ nodes.my-loop.output.iterations }}`
- `{{ nodes.my-loop.output.results[0].status }}`

## Error Handling

By default, the loop continues if an iteration fails. The loop node itself fails only if a critical error occurs.

### Fail Fast

To stop on first error, add error handling in body nodes:

```yaml
- id: strict-loop
  type: loop
  config:
    items: ["a", "b", "c"]
    body:
      - id: process
        type: shell
        config:
          command: "./process.sh {{ item }}"
        retry:
          max_attempts: 1  # No retries, fail immediately
```

### Collect Failures

```yaml
- id: process-all
  type: loop
  config:
    items: "{{ input.items }}"
    body:
      - id: try-process
        type: shell
        config:
          command: "./process.sh {{ item }}"

- id: check-failures
  type: condition
  config:
    expression: "{{ nodes.process-all.output.failed > 0 }}"
    then_branch: report-failures
    else_branch: success
  depends_on:
    - process-all
```

## Best Practices

1. **Limit parallelism** for resource-intensive operations
2. **Use meaningful variable names** (`user` vs `item`)
3. **Handle failures** appropriately for your use case
4. **Keep loop bodies simple** - extract complex logic to separate workflows
5. **Monitor performance** with many iterations

# Condition Node

Branch workflow execution based on conditions.

## Configuration

```yaml
- id: my-condition
  type: condition
  config:
    expression: string     # Required: boolean expression to evaluate
    then_branch: string    # Required: node ID to execute if true
    else_branch: string    # Optional: node ID to execute if false
```

## Examples

### Simple Condition

```yaml
- id: check-env
  type: condition
  config:
    expression: "{{ env('ENVIRONMENT') == 'production' }}"
    then_branch: deploy-prod
    else_branch: deploy-staging

- id: deploy-prod
  type: shell
  config:
    command: ./deploy.sh production

- id: deploy-staging
  type: shell
  config:
    command: ./deploy.sh staging
```

### Check Previous Node Status

```yaml
- id: api-call
  type: http
  config:
    url: https://api.example.com/data

- id: check-success
  type: condition
  config:
    expression: "{{ nodes.api-call.output.status_code == 200 }}"
    then_branch: process-data
    else_branch: handle-error
  depends_on:
    - api-call

- id: process-data
  type: shell
  config:
    command: echo "Processing data..."

- id: handle-error
  type: shell
  config:
    command: echo "API call failed"
```

### Check Input Values

```yaml
- id: check-input
  type: condition
  config:
    expression: "{{ input.action == 'deploy' }}"
    then_branch: do-deploy
    else_branch: skip-deploy

- id: do-deploy
  type: shell
  config:
    command: ./deploy.sh

- id: skip-deploy
  type: log
  config:
    message: "Deployment skipped"
    level: info
```

### Numeric Comparisons

```yaml
- id: fetch-metrics
  type: http
  config:
    url: https://api.example.com/metrics

- id: check-threshold
  type: condition
  config:
    expression: "{{ nodes.fetch-metrics.output.body.cpu_usage > 80 }}"
    then_branch: alert-high-cpu
    else_branch: log-normal
  depends_on:
    - fetch-metrics

- id: alert-high-cpu
  type: http
  config:
    url: https://alerts.example.com/send
    method: POST
    body:
      message: "High CPU usage detected"
      severity: warning

- id: log-normal
  type: log
  config:
    message: "CPU usage normal"
```

### Multiple Conditions (Chained)

```yaml
- id: check-priority
  type: condition
  config:
    expression: "{{ input.priority == 'high' }}"
    then_branch: urgent-process
    else_branch: check-medium

- id: check-medium
  type: condition
  config:
    expression: "{{ input.priority == 'medium' }}"
    then_branch: normal-process
    else_branch: low-priority-process

- id: urgent-process
  type: shell
  config:
    command: ./process.sh --urgent

- id: normal-process
  type: shell
  config:
    command: ./process.sh

- id: low-priority-process
  type: shell
  config:
    command: ./process.sh --batch
```

### Boolean Logic

```yaml
- id: complex-check
  type: condition
  config:
    expression: |
      {{
        (input.type == 'release' and env('ENVIRONMENT') == 'production')
        or input.force == true
      }}
    then_branch: do-release
    else_branch: skip-release
```

## Expression Syntax

Conditions support Jinja2-style expressions:

### Comparison Operators
- `==`, `!=` - Equality
- `<`, `>`, `<=`, `>=` - Numeric comparison
- `in`, `not in` - Membership

### Logical Operators
- `and`, `or`, `not`

### Examples
```
{{ value == 'expected' }}
{{ count > 10 }}
{{ item in ['a', 'b', 'c'] }}
{{ status == 'success' and count > 0 }}
{{ not is_disabled }}
```

## Output

The condition node outputs:

```json
{
  "expression": "input.enabled == true",
  "result": true,
  "branch_taken": "then_branch"
}
```

## Error Handling

A condition node fails if:
- The expression cannot be evaluated
- Referenced node or value doesn't exist

Always ensure referenced values exist:

```yaml
- id: safe-check
  type: condition
  config:
    expression: "{{ nodes.api-call.output.body.data | default([]) | length > 0 }}"
    then_branch: process-data
    else_branch: no-data
```

## Best Practices

1. **Keep expressions simple** - Complex logic is hard to debug
2. **Use default values** to handle missing data
3. **Document complex conditions** in workflow description
4. **Chain conditions** instead of deeply nested logic
5. **Test both branches** to ensure they execute correctly

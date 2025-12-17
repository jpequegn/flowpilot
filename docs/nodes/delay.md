# Delay Node

Pause workflow execution for a specified duration.

## Configuration

```yaml
- id: my-delay
  type: delay
  config:
    seconds: number       # Required: delay duration in seconds
```

## Examples

### Simple Delay

```yaml
- id: wait
  type: delay
  config:
    seconds: 5
```

### Rate Limiting

```yaml
- id: api-call-1
  type: http
  config:
    url: https://api.example.com/data/1

- id: rate-limit
  type: delay
  config:
    seconds: 1
  depends_on:
    - api-call-1

- id: api-call-2
  type: http
  config:
    url: https://api.example.com/data/2
  depends_on:
    - rate-limit
```

### Polling Pattern

```yaml
- id: start-job
  type: http
  config:
    url: https://api.example.com/jobs
    method: POST
    body:
      task: process-data

- id: wait-for-processing
  type: delay
  config:
    seconds: 30
  depends_on:
    - start-job

- id: check-status
  type: http
  config:
    url: "https://api.example.com/jobs/{{ nodes.start-job.output.body.job_id }}"
  depends_on:
    - wait-for-processing
```

### Dynamic Delay

```yaml
- id: configurable-wait
  type: delay
  config:
    seconds: "{{ input.wait_time | default(10) }}"
```

### Exponential Backoff (Manual)

```yaml
- id: attempt-1
  type: http
  config:
    url: https://api.example.com/data

- id: check-1
  type: condition
  config:
    expression: "{{ nodes.attempt-1.status == 'failed' }}"
    then_branch: delay-1
    else_branch: success
  depends_on:
    - attempt-1

- id: delay-1
  type: delay
  config:
    seconds: 2

- id: attempt-2
  type: http
  config:
    url: https://api.example.com/data
  depends_on:
    - delay-1

- id: check-2
  type: condition
  config:
    expression: "{{ nodes.attempt-2.status == 'failed' }}"
    then_branch: delay-2
    else_branch: success
  depends_on:
    - attempt-2

- id: delay-2
  type: delay
  config:
    seconds: 4

- id: attempt-3
  type: http
  config:
    url: https://api.example.com/data
  depends_on:
    - delay-2

- id: success
  type: log
  config:
    message: "Request succeeded"
```

### Coordination Delay

```yaml
- id: deploy-service-a
  type: shell
  config:
    command: ./deploy.sh service-a

- id: wait-for-health
  type: delay
  config:
    seconds: 30
  depends_on:
    - deploy-service-a

- id: deploy-service-b
  type: shell
  config:
    command: ./deploy.sh service-b
  depends_on:
    - wait-for-health
```

## Output

The delay node outputs:

```json
{
  "seconds": 5,
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:05Z"
}
```

## Use Cases

### Rate Limiting
Prevent hitting API rate limits by adding delays between requests.

### Service Startup
Wait for services to become healthy after deployment.

### Polling
Periodically check status of long-running operations.

### Coordination
Ensure services have time to initialize before dependent operations.

### Testing
Simulate latency or timeouts in development workflows.

## Best Practices

1. **Use appropriate durations** - Don't delay longer than necessary
2. **Consider retry mechanisms** instead of fixed delays for error handling
3. **Document why delays exist** in workflow description
4. **Use health checks** instead of arbitrary delays when possible
5. **Keep delays short in development** - Use variables to configure per environment

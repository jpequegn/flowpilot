# Shell Node

Execute shell commands on your system.

## Configuration

```yaml
- id: my-shell-node
  type: shell
  config:
    command: string       # Required: command to execute
    shell: string         # Optional: shell to use (default: /bin/sh)
    timeout: integer      # Optional: timeout in seconds
    working_dir: string   # Optional: working directory
    env:                  # Optional: environment variables
      KEY: value
```

## Examples

### Basic Command

```yaml
- id: list-files
  type: shell
  config:
    command: ls -la
```

### Command with Variables

```yaml
- id: greet
  type: shell
  config:
    command: echo "Hello, {{ env('USER') }}!"
```

### Multi-line Script

```yaml
- id: setup
  type: shell
  config:
    command: |
      echo "Starting setup..."
      mkdir -p ~/backups
      echo "Setup complete"
```

### With Working Directory

```yaml
- id: build
  type: shell
  config:
    command: npm run build
    working_dir: /path/to/project
```

### With Environment Variables

```yaml
- id: deploy
  type: shell
  config:
    command: ./deploy.sh
    env:
      ENVIRONMENT: production
      DEBUG: "false"
```

### With Timeout

```yaml
- id: long-running
  type: shell
  config:
    command: ./process-data.sh
    timeout: 300  # 5 minutes
```

### Using Previous Node Output

```yaml
- id: fetch-url
  type: http
  config:
    url: https://api.example.com/download-url
    method: GET

- id: download
  type: shell
  config:
    command: curl -o file.zip "{{ nodes.fetch-url.output.body.url }}"
  depends_on:
    - fetch-url
```

## Output

The shell node outputs:

```json
{
  "stdout": "command output",
  "stderr": "error output if any",
  "exit_code": 0,
  "duration_ms": 150
}
```

Access in templates:
- `{{ nodes.my-node.output.stdout }}`
- `{{ nodes.my-node.output.exit_code }}`

## Error Handling

A shell node fails if:
- The command returns a non-zero exit code
- The command times out
- The shell cannot execute the command

```yaml
- id: check-file
  type: shell
  config:
    command: test -f /path/to/file
  retry:
    max_attempts: 3
    delay_seconds: 2

- id: fallback
  type: shell
  config:
    command: echo "File not found, using default"
  condition: "{{ nodes.check-file.status == 'failed' }}"
```

## Security Notes

- Commands execute with the same permissions as the FlowPilot process
- Be careful with user-provided input in templates
- Validate and sanitize any external data before using in commands
- Consider using dedicated service accounts for production

## Best Practices

1. **Use explicit paths** for important commands
2. **Set timeouts** for potentially long-running commands
3. **Handle errors** with conditions or retries
4. **Log output** for debugging with the log node
5. **Avoid secrets** in command strings - use environment variables

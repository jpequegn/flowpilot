# File Nodes

Read and write files on your system.

## File Read Node

Read content from a file.

### Configuration

```yaml
- id: my-file-read
  type: file_read
  config:
    path: string        # Required: path to file
    encoding: string    # Optional: encoding (default: utf-8)
```

### Examples

#### Read Text File

```yaml
- id: read-config
  type: file_read
  config:
    path: /path/to/config.json
```

#### Read with Dynamic Path

```yaml
- id: read-user-data
  type: file_read
  config:
    path: "{{ env('HOME') }}/data/{{ input.filename }}"
```

#### Read and Process

```yaml
- id: read-data
  type: file_read
  config:
    path: /data/input.json

- id: process
  type: shell
  config:
    command: |
      echo '{{ nodes.read-data.output.content }}' | jq '.items | length'
  depends_on:
    - read-data
```

### Output

```json
{
  "content": "file contents as string",
  "path": "/absolute/path/to/file",
  "size": 1234,
  "modified": "2024-01-15T10:30:00Z"
}
```

Access in templates:
- `{{ nodes.read-config.output.content }}`
- `{{ nodes.read-config.output.size }}`

---

## File Write Node

Write content to a file.

### Configuration

```yaml
- id: my-file-write
  type: file_write
  config:
    path: string        # Required: path to file
    content: string     # Required: content to write
    mode: string        # Optional: write|append (default: write)
    encoding: string    # Optional: encoding (default: utf-8)
    create_dirs: bool   # Optional: create parent directories (default: true)
```

### Examples

#### Write Text File

```yaml
- id: write-output
  type: file_write
  config:
    path: /tmp/output.txt
    content: "Hello, World!"
```

#### Write with Template

```yaml
- id: write-report
  type: file_write
  config:
    path: /reports/daily-{{ now('%Y-%m-%d') }}.txt
    content: |
      Daily Report
      Generated: {{ now() }}

      Results: {{ nodes.process.output.stdout }}
```

#### Append to File

```yaml
- id: append-log
  type: file_write
  config:
    path: /var/log/workflow.log
    content: "[{{ now() }}] Workflow completed\n"
    mode: append
```

#### Write JSON

```yaml
- id: save-results
  type: file_write
  config:
    path: /data/results.json
    content: |
      {
        "timestamp": "{{ now() }}",
        "status": "{{ nodes.process.status }}",
        "data": {{ nodes.fetch.output.body | tojson }}
      }
```

#### Create Backup

```yaml
- id: backup-config
  type: file_read
  config:
    path: /etc/myapp/config.yaml

- id: save-backup
  type: file_write
  config:
    path: /backups/config-{{ now('%Y%m%d-%H%M%S') }}.yaml
    content: "{{ nodes.backup-config.output.content }}"
    create_dirs: true
  depends_on:
    - backup-config
```

### Output

```json
{
  "path": "/absolute/path/to/file",
  "size": 1234,
  "mode": "write"
}
```

## Error Handling

File nodes fail if:
- **file_read**: File doesn't exist or isn't readable
- **file_write**: Can't create or write to file

```yaml
- id: try-read
  type: file_read
  config:
    path: /optional/config.json

- id: use-default
  type: shell
  config:
    command: echo "Using default configuration"
  condition: "{{ nodes.try-read.status == 'failed' }}"
```

## Security Notes

- File operations use the process user's permissions
- Be careful with paths from user input
- Validate paths to prevent directory traversal attacks
- Consider using absolute paths

## Best Practices

1. **Use absolute paths** when possible
2. **Enable create_dirs** for dynamic output paths
3. **Include timestamps** in backup file names
4. **Handle missing files** gracefully with conditions
5. **Log file operations** for audit trails

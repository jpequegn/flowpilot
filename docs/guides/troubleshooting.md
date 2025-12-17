# Troubleshooting

Common issues and solutions for FlowPilot.

## Installation Issues

### Command not found: flowpilot

**Symptom:** After installation, `flowpilot` command is not recognized.

**Solutions:**

1. **Check installation:**
   ```bash
   pip show flowpilot
   ```

2. **Add to PATH:**
   ```bash
   # Check where pip installs scripts
   python -m site --user-base

   # Add to PATH (bash/zsh)
   export PATH="$PATH:$(python -m site --user-base)/bin"
   ```

3. **Use module syntax:**
   ```bash
   python -m flowpilot --help
   ```

### Import errors

**Symptom:** `ModuleNotFoundError` when running FlowPilot.

**Solution:** Ensure all dependencies are installed:
```bash
pip install flowpilot[all]
# Or reinstall
pip install --force-reinstall flowpilot
```

---

## Server Issues

### Port already in use

**Symptom:** `Address already in use` when starting server.

**Solutions:**

1. **Use different port:**
   ```bash
   flowpilot serve --port 9000
   ```

2. **Find and kill existing process:**
   ```bash
   lsof -i :8080
   kill -9 <PID>
   ```

### Server won't start

**Symptom:** Server exits immediately without error.

**Solutions:**

1. **Check logs:**
   ```bash
   flowpilot serve --verbose
   ```

2. **Verify database:**
   ```bash
   # Reset database
   rm flowpilot.db
   flowpilot init
   ```

3. **Check workflows directory:**
   ```bash
   ls -la workflows/
   ```

---

## Workflow Issues

### Workflow not found

**Symptom:** `Workflow not found: workflow-name`

**Solutions:**

1. **Check workflow exists:**
   ```bash
   ls workflows/
   ```

2. **Verify workflow name matches file:**
   ```yaml
   # In workflows/my-workflow.yaml
   name: my-workflow  # This is what you use to run
   ```

3. **Check YAML syntax:**
   ```bash
   python -c "import yaml; yaml.safe_load(open('workflows/my-workflow.yaml'))"
   ```

### Invalid YAML syntax

**Symptom:** `yaml.scanner.ScannerError` or similar.

**Common causes:**

1. **Indentation errors:**
   ```yaml
   # Wrong
   nodes:
   - id: step1
     type: shell

   # Correct
   nodes:
     - id: step1
       type: shell
   ```

2. **Missing quotes around special characters:**
   ```yaml
   # Wrong - : has special meaning
   command: echo: hello

   # Correct
   command: "echo: hello"
   ```

3. **Invalid template syntax:**
   ```yaml
   # Wrong - missing closing brace
   command: echo "{{ input.name }"

   # Correct
   command: echo "{{ input.name }}"
   ```

### Node dependency cycle

**Symptom:** `Circular dependency detected`

**Solution:** Review `depends_on` references:
```yaml
# Wrong - circular dependency
nodes:
  - id: a
    depends_on: [b]
  - id: b
    depends_on: [a]

# Correct - clear order
nodes:
  - id: a
  - id: b
    depends_on: [a]
```

---

## Execution Issues

### Shell command fails

**Symptom:** Shell node returns non-zero exit code.

**Debugging steps:**

1. **Check command manually:**
   ```bash
   # Run the command in terminal
   echo "Hello"
   ```

2. **Check environment:**
   ```yaml
   - id: debug-env
     type: shell
     config:
       command: env | sort
   ```

3. **Add error handling:**
   ```yaml
   - id: safe-command
     type: shell
     config:
       command: ./script.sh || echo "Failed but continuing"
   ```

### HTTP request fails

**Symptom:** HTTP node returns error or unexpected response.

**Debugging steps:**

1. **Test URL manually:**
   ```bash
   curl -v https://api.example.com/data
   ```

2. **Check authentication:**
   ```yaml
   - id: debug-auth
     type: log
     config:
       message: "Token: {{ env('API_TOKEN') | default('NOT SET') }}"
   ```

3. **Log response:**
   ```yaml
   - id: log-response
     type: log
     config:
       message: "Response: {{ nodes.api-call.output | tojson }}"
   ```

### Template not rendering

**Symptom:** Output shows literal `{{ }}` instead of values.

**Solutions:**

1. **Check syntax:**
   ```yaml
   # Wrong - not in quotes
   command: echo {{ input.name }}

   # Correct
   command: echo "{{ input.name }}"
   ```

2. **Verify data exists:**
   ```yaml
   - id: debug
     type: log
     config:
       message: "Input: {{ input | tojson }}"
   ```

3. **Use default values:**
   ```yaml
   message: "{{ input.name | default('No name') }}"
   ```

---

## Claude Node Issues

### Claude CLI not found

**Symptom:** `claude_cli` node fails with command not found.

**Solution:**
```bash
# Install Claude CLI
npm install -g @anthropic-ai/claude-cli

# Verify
claude --version
```

### API key invalid

**Symptom:** `claude_api` node returns authentication error.

**Solution:**
```bash
# Set API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Verify it's set
echo $ANTHROPIC_API_KEY
```

### Rate limits

**Symptom:** `Rate limit exceeded` errors.

**Solutions:**

1. **Add retry logic:**
   ```yaml
   - id: ai-task
     type: claude_api
     config:
       prompt: "..."
     retry:
       max_attempts: 3
       delay_seconds: 30
       backoff_multiplier: 2
   ```

2. **Reduce request frequency:**
   ```yaml
   - id: delay
     type: delay
     config:
       seconds: 5
     depends_on:
       - previous-ai-call
   ```

---

## Performance Issues

### Slow workflow execution

**Possible causes:**

1. **Sequential when could be parallel:**
   ```yaml
   # Slow - runs one by one
   - id: task-1
   - id: task-2
     depends_on: [task-1]  # Unnecessary dependency

   # Fast - runs in parallel
   - id: task-1
   - id: task-2  # No dependency, runs with task-1
   ```

2. **Too many API calls:**
   - Batch requests where possible
   - Add caching
   - Use parallel node with `max_concurrent`

3. **Large file operations:**
   - Process files in chunks
   - Use streaming where available

### High memory usage

**Solutions:**

1. **Process data in batches:**
   ```yaml
   - id: process
     type: loop
     config:
       items: "{{ input.items }}"
       max_parallel: 5  # Limit concurrency
   ```

2. **Avoid loading large files entirely:**
   ```bash
   # Instead of loading entire file
   head -1000 large-file.txt | process
   ```

---

## Database Issues

### Database locked

**Symptom:** `database is locked` error.

**Solutions:**

1. **Check for stuck processes:**
   ```bash
   lsof flowpilot.db
   ```

2. **Reset database:**
   ```bash
   mv flowpilot.db flowpilot.db.backup
   flowpilot init
   ```

### Corrupted database

**Symptom:** `database disk image is malformed`

**Solution:**
```bash
# Try to recover
sqlite3 flowpilot.db ".recover" > recovered.sql
rm flowpilot.db
sqlite3 flowpilot.db < recovered.sql
```

---

## Getting Help

### Debug Mode

Run with verbose logging:
```bash
# CLI
flowpilot run workflow --verbose

# Server
FLOWPILOT_LOG_LEVEL=DEBUG flowpilot serve
```

### Check Logs

```bash
# View recent executions
flowpilot executions --limit 10

# View specific execution
flowpilot execution <id> --logs
```

### Report Issues

When reporting issues, include:
1. FlowPilot version: `flowpilot --version`
2. Python version: `python --version`
3. Operating system
4. Workflow YAML (sanitized)
5. Error message or logs
6. Steps to reproduce

File issues at: https://github.com/jpequegn/flowpilot/issues

---

## See Also

- [Configuration](../getting-started/configuration.md)
- [CLI Reference](../cli/)
- [API Reference](../api/)

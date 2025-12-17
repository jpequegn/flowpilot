# Example Workflows

This section contains example workflows demonstrating various FlowPilot capabilities.

## Examples Index

| Example | Description | Features |
|---------|-------------|----------|
| [Daily Code Review](daily-code-review.md) | Automated PR review with Claude | Claude CLI, GitHub API, scheduling |
| [GitHub Webhook Handler](github-webhook-handler.md) | Process GitHub events | HTTP, conditions, file operations |
| [File Backup](file-backup.md) | Automated backup system | Shell, cron, file operations |
| [Parallel API Fetcher](parallel-api-fetcher.md) | Fetch from multiple APIs concurrently | Parallel, HTTP, data aggregation |
| [Data Processing Pipeline](data-pipeline.md) | ETL workflow | Loops, conditions, Claude API |

## Running Examples

1. Copy the example workflow to your workflows directory
2. Adjust configuration (paths, URLs, credentials)
3. Run with FlowPilot:

```bash
# Run directly
flowpilot run example-name

# With input
flowpilot run example-name --input '{"key": "value"}'

# Via web UI
flowpilot serve
# Then navigate to http://localhost:8080
```

## Example Categories

### Automation
- File backups and synchronization
- System maintenance tasks
- Scheduled reports

### Integration
- API orchestration
- Webhook processing
- Service coordination

### AI-Powered
- Code review and analysis
- Content generation
- Data transformation

### Data Processing
- ETL pipelines
- Log analysis
- Batch processing

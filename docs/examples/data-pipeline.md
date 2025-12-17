# Data Processing Pipeline

ETL (Extract, Transform, Load) workflow with AI-powered data analysis.

## Overview

This workflow:
1. Extracts data from a source (API or file)
2. Validates and cleans the data
3. Transforms using Claude for intelligent processing
4. Loads results to destination
5. Generates a summary report

## Workflow

```yaml
name: data-pipeline
description: ETL pipeline with AI-powered transformation

triggers:
  - type: cron
    schedule: "0 6 * * *"  # Daily at 6 AM
  - type: manual

nodes:
  # ============= EXTRACT =============
  - id: extract-data
    type: http
    config:
      url: "{{ env('DATA_SOURCE_URL') }}/export"
      method: GET
      headers:
        Authorization: "Bearer {{ env('DATA_API_KEY') }}"
      timeout: 120

  - id: log-extract
    type: log
    config:
      message: "Extracted {{ nodes.extract-data.output.body.records | length }} records"
      level: info
    depends_on:
      - extract-data

  # ============= VALIDATE =============
  - id: validate-data
    type: loop
    config:
      items: "{{ nodes.extract-data.output.body.records }}"
      item_var: record
      max_parallel: 5
      body:
        - id: check-required-fields
          type: condition
          config:
            expression: |
              {{
                record.id is defined and
                record.timestamp is defined and
                record.value is defined
              }}
            then_branch: mark-valid
            else_branch: mark-invalid

        - id: mark-valid
          type: log
          config:
            message: "Valid record: {{ record.id }}"
            level: debug

        - id: mark-invalid
          type: log
          config:
            message: "Invalid record (missing fields): {{ record | tojson }}"
            level: warning
    depends_on:
      - extract-data

  - id: filter-valid
    type: shell
    config:
      command: |
        # Filter to only valid records
        echo '{{ nodes.extract-data.output.body.records | selectattr("id", "defined") | selectattr("timestamp", "defined") | selectattr("value", "defined") | list | tojson }}'
    depends_on:
      - validate-data

  # ============= TRANSFORM =============
  - id: transform-data
    type: claude_api
    config:
      system: |
        You are a data analyst. Transform the input data according to these rules:
        1. Normalize timestamps to ISO 8601 format
        2. Convert values to numeric types
        3. Add a "category" field based on value ranges:
           - "low" for values < 100
           - "medium" for values 100-500
           - "high" for values > 500
        4. Output valid JSON array

        Only output the JSON, no explanation.
      prompt: |
        Transform this data:
        {{ nodes.filter-valid.output.stdout }}
      temperature: 0
    depends_on:
      - filter-valid

  - id: parse-transformed
    type: shell
    config:
      command: |
        echo '{{ nodes.transform-data.output.response }}' | jq '.'
    depends_on:
      - transform-data

  # ============= ANALYZE =============
  - id: analyze-data
    type: claude_api
    config:
      system: |
        You are a data analyst. Analyze the provided data and generate insights.
        Include:
        1. Summary statistics
        2. Trends or patterns
        3. Anomalies or outliers
        4. Recommendations

        Be concise and actionable.
      prompt: |
        Analyze this data:
        {{ nodes.parse-transformed.output.stdout }}
      temperature: 0.3
    depends_on:
      - parse-transformed

  # ============= LOAD =============
  - id: save-transformed
    type: file_write
    config:
      path: "/data/output/transformed-{{ now('%Y%m%d') }}.json"
      content: "{{ nodes.parse-transformed.output.stdout }}"
      create_dirs: true
    depends_on:
      - parse-transformed

  - id: save-analysis
    type: file_write
    config:
      path: "/data/output/analysis-{{ now('%Y%m%d') }}.md"
      content: |
        # Data Analysis Report

        Generated: {{ now() }}

        ## Summary

        {{ nodes.analyze-data.output.response }}

        ## Data Source

        - Records processed: {{ nodes.extract-data.output.body.records | length }}
        - Valid records: {{ nodes.filter-valid.output.stdout | fromjson | length }}
      create_dirs: true
    depends_on:
      - analyze-data

  # ============= NOTIFY =============
  - id: send-notification
    type: http
    config:
      url: "{{ env('SLACK_WEBHOOK_URL') }}"
      method: POST
      body:
        text: |
          📊 Daily Data Pipeline Complete

          Records processed: {{ nodes.extract-data.output.body.records | length }}
          Valid records: {{ nodes.filter-valid.output.stdout | fromjson | length }}

          Analysis highlights:
          {{ nodes.analyze-data.output.response | truncate(500) }}
    condition: "{{ env('SLACK_WEBHOOK_URL') != '' }}"
    depends_on:
      - save-analysis

  - id: log-complete
    type: log
    config:
      message: "Pipeline complete. Output saved to /data/output/"
      level: info
    depends_on:
      - save-transformed
      - save-analysis
```

## Simpler Version

Without AI transformation:

```yaml
name: simple-etl
description: Basic ETL pipeline

nodes:
  - id: extract
    type: http
    config:
      url: "{{ env('SOURCE_URL') }}"

  - id: transform
    type: shell
    config:
      command: |
        echo '{{ nodes.extract.output.body | tojson }}' | jq '
          .records |
          map(select(.status == "active")) |
          map({
            id: .id,
            name: .name,
            value: (.amount | tonumber)
          })
        '
    depends_on:
      - extract

  - id: load
    type: http
    config:
      url: "{{ env('DEST_URL') }}"
      method: POST
      body: "{{ nodes.transform.output.stdout | fromjson }}"
    depends_on:
      - transform
```

## With Database Load

```yaml
  - id: load-to-db
    type: shell
    config:
      command: |
        echo '{{ nodes.transform.output.stdout }}' | \
        psql "$DATABASE_URL" -c "
          COPY data_table FROM STDIN WITH (FORMAT json);
        "
    depends_on:
      - transform
```

## Configuration

### Environment Variables

```bash
export DATA_SOURCE_URL="https://api.example.com"
export DATA_API_KEY="your-api-key"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx"
export ANTHROPIC_API_KEY="sk-ant-xxx"  # For Claude nodes
```

## Best Practices

1. **Validate early** - Catch bad data before transformation
2. **Log progress** - Track each stage for debugging
3. **Handle failures** - Use retries and fallbacks
4. **Save intermediate results** - Aid debugging and recovery
5. **Monitor performance** - Track duration of each stage
6. **Use incremental processing** - Don't reprocess everything

## Extending the Pipeline

### Add Deduplication

```yaml
  - id: deduplicate
    type: shell
    config:
      command: |
        echo '{{ nodes.extract.output.body | tojson }}' | \
        jq 'unique_by(.id)'
```

### Add Data Quality Checks

```yaml
  - id: quality-check
    type: condition
    config:
      expression: "{{ nodes.validate.output.valid_count > nodes.validate.output.total * 0.9 }}"
      then_branch: continue-pipeline
      else_branch: alert-bad-data
```

## Related Examples

- [Parallel API Fetcher](parallel-api-fetcher.md) - Fetch from multiple sources
- [File Backup](file-backup.md) - Save processed data

# Parallel API Fetcher

Fetch data from multiple APIs concurrently and aggregate results.

## Overview

This workflow:
1. Fetches data from multiple APIs in parallel
2. Transforms and normalizes responses
3. Aggregates into a single report
4. Optionally sends to a webhook or saves to file

## Workflow

```yaml
name: parallel-api-fetcher
description: Fetch and aggregate data from multiple APIs

triggers:
  - type: cron
    schedule: "*/15 * * * *"  # Every 15 minutes
  - type: manual

nodes:
  - id: log-start
    type: log
    config:
      message: "Starting data collection at {{ now() }}"
      level: info

  - id: fetch-all
    type: parallel
    config:
      branches:
        - id: weather
          nodes:
            - id: fetch-weather
              type: http
              config:
                url: "https://api.openweathermap.org/data/2.5/weather"
                method: GET
                headers:
                  Accept: application/json
              retry:
                max_attempts: 3
                delay_seconds: 2

        - id: news
          nodes:
            - id: fetch-news
              type: http
              config:
                url: "https://newsapi.org/v2/top-headlines?country=us"
                method: GET
                headers:
                  X-Api-Key: "{{ env('NEWS_API_KEY') }}"
              retry:
                max_attempts: 3
                delay_seconds: 2

        - id: stocks
          nodes:
            - id: fetch-stocks
              type: http
              config:
                url: "https://api.example.com/v1/stocks/summary"
                method: GET
                headers:
                  Authorization: "Bearer {{ env('STOCK_API_KEY') }}"
              retry:
                max_attempts: 3
                delay_seconds: 2

        - id: crypto
          nodes:
            - id: fetch-crypto
              type: http
              config:
                url: "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd"
                method: GET
              retry:
                max_attempts: 3
                delay_seconds: 2
    depends_on:
      - log-start

  - id: log-fetched
    type: log
    config:
      message: "Fetched data from {{ nodes.fetch-all.output.completed }} sources"
      level: info
    depends_on:
      - fetch-all

  - id: aggregate-data
    type: shell
    config:
      command: |
        cat << 'EOF'
        {
          "timestamp": "{{ now() }}",
          "sources": {
            "weather": {{ nodes.fetch-all.branches.weather.fetch-weather.output.body | default({}) | tojson }},
            "crypto": {{ nodes.fetch-all.branches.crypto.fetch-crypto.output.body | default({}) | tojson }}
          },
          "status": {
            "completed": {{ nodes.fetch-all.output.completed }},
            "failed": {{ nodes.fetch-all.output.failed }}
          }
        }
        EOF
    depends_on:
      - fetch-all

  - id: save-report
    type: file_write
    config:
      path: "/tmp/api-report-{{ now('%Y%m%d-%H%M%S') }}.json"
      content: "{{ nodes.aggregate-data.output.stdout }}"
    depends_on:
      - aggregate-data

  - id: log-complete
    type: log
    config:
      message: "Data aggregation complete. Report saved."
      level: info
    depends_on:
      - save-report
```

## With Error Handling

Handle individual API failures gracefully:

```yaml
name: resilient-api-fetcher
description: Fetch with graceful degradation

nodes:
  - id: fetch-all
    type: parallel
    config:
      branches:
        - id: primary-api
          nodes:
            - id: fetch-primary
              type: http
              config:
                url: "{{ env('PRIMARY_API_URL') }}"
              retry:
                max_attempts: 2
                delay_seconds: 1

            - id: primary-fallback
              type: http
              config:
                url: "{{ env('BACKUP_API_URL') }}"
              condition: "{{ nodes.fetch-primary.status == 'failed' }}"
              depends_on:
                - fetch-primary

        - id: secondary-api
          nodes:
            - id: fetch-secondary
              type: http
              config:
                url: "{{ env('SECONDARY_API_URL') }}"
              retry:
                max_attempts: 2

  - id: check-results
    type: condition
    config:
      expression: "{{ nodes.fetch-all.output.failed == 0 }}"
      then_branch: all-success
      else_branch: partial-success
    depends_on:
      - fetch-all

  - id: all-success
    type: log
    config:
      message: "All APIs responded successfully"
      level: info

  - id: partial-success
    type: log
    config:
      message: "Some APIs failed: {{ nodes.fetch-all.output.failed }} failures"
      level: warning
```

## Rate-Limited Version

For APIs with rate limits:

```yaml
name: rate-limited-fetcher
description: Fetch with rate limiting

nodes:
  - id: fetch-items
    type: loop
    config:
      items:
        - "https://api.example.com/item/1"
        - "https://api.example.com/item/2"
        - "https://api.example.com/item/3"
        - "https://api.example.com/item/4"
        - "https://api.example.com/item/5"
      item_var: url
      max_parallel: 2  # Only 2 concurrent requests
      body:
        - id: fetch
          type: http
          config:
            url: "{{ url }}"

        - id: rate-limit
          type: delay
          config:
            seconds: 1  # Wait 1 second between requests
          depends_on:
            - fetch
```

## Configuration

### Environment Variables

```bash
export NEWS_API_KEY="your-news-api-key"
export STOCK_API_KEY="your-stock-api-key"
export PRIMARY_API_URL="https://api.example.com/v1/data"
export BACKUP_API_URL="https://backup.example.com/v1/data"
```

## Use Cases

- **Dashboard data aggregation** - Collect data for a unified view
- **Price monitoring** - Track prices across multiple sources
- **Health checks** - Monitor multiple services simultaneously
- **Data enrichment** - Combine data from multiple APIs

## Best Practices

1. **Set timeouts** - Don't let slow APIs block others
2. **Use retries** - Handle transient failures
3. **Implement fallbacks** - Have backup data sources
4. **Rate limit requests** - Respect API limits
5. **Cache responses** - Reduce redundant calls
6. **Monitor failures** - Alert on repeated issues

## Related Examples

- [Data Processing Pipeline](data-pipeline.md) - Process fetched data
- [GitHub Webhook Handler](github-webhook-handler.md) - Event-driven fetching

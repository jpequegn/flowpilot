# Claude Nodes

AI-powered nodes using Claude CLI or Anthropic API.

## Claude CLI Node

Execute prompts using the Claude CLI.

### Configuration

```yaml
- id: my-claude-cli
  type: claude_cli
  config:
    prompt: string        # Required: prompt to send
    model: string         # Optional: model to use
    max_tokens: integer   # Optional: max response tokens
    system: string        # Optional: system prompt
```

### Prerequisites

- Claude CLI installed: `npm install -g @anthropic-ai/claude-cli`
- Anthropic API key configured

### Examples

#### Basic Prompt

```yaml
- id: generate-summary
  type: claude_cli
  config:
    prompt: "Summarize this text in 3 bullet points: {{ input.text }}"
```

#### With System Prompt

```yaml
- id: code-review
  type: claude_cli
  config:
    system: "You are an expert code reviewer. Be concise and focus on critical issues."
    prompt: |
      Review this code and identify potential bugs or improvements:

      ```
      {{ nodes.read-code.output.content }}
      ```
```

#### Analyze API Response

```yaml
- id: fetch-data
  type: http
  config:
    url: https://api.example.com/metrics

- id: analyze-metrics
  type: claude_cli
  config:
    prompt: |
      Analyze these system metrics and identify any anomalies:
      {{ nodes.fetch-data.output.body | tojson }}
  depends_on:
    - fetch-data
```

#### Generate Documentation

```yaml
- id: read-function
  type: file_read
  config:
    path: "{{ input.file_path }}"

- id: generate-docs
  type: claude_cli
  config:
    system: "You are a technical writer. Generate clear, concise documentation."
    prompt: |
      Generate documentation for this function:

      {{ nodes.read-function.output.content }}
  depends_on:
    - read-function
```

---

## Claude API Node

Make direct API calls to Anthropic's API.

### Configuration

```yaml
- id: my-claude-api
  type: claude_api
  config:
    prompt: string        # Required: prompt to send
    model: string         # Optional: model (default: claude-3-sonnet-20240229)
    max_tokens: integer   # Optional: max response tokens (default: 1024)
    system: string        # Optional: system prompt
    temperature: number   # Optional: response randomness (0-1)
```

### Prerequisites

- Set `ANTHROPIC_API_KEY` environment variable

### Examples

#### Basic API Call

```yaml
- id: classify-text
  type: claude_api
  config:
    prompt: |
      Classify this customer feedback as positive, negative, or neutral:
      "{{ input.feedback }}"

      Respond with only: positive, negative, or neutral
    temperature: 0
```

#### Multi-Step Analysis

```yaml
- id: extract-entities
  type: claude_api
  config:
    prompt: |
      Extract all company names mentioned in this text:
      {{ input.text }}

      Return as JSON array.
    temperature: 0

- id: enrich-entities
  type: claude_api
  config:
    prompt: |
      For each company, provide a brief description:
      {{ nodes.extract-entities.output.response }}
  depends_on:
    - extract-entities
```

#### Data Transformation

```yaml
- id: fetch-data
  type: http
  config:
    url: https://api.example.com/raw-data

- id: transform-data
  type: claude_api
  config:
    system: "Transform data as requested. Output only valid JSON."
    prompt: |
      Transform this data into a simplified format with only id, name, and status fields:
      {{ nodes.fetch-data.output.body | tojson }}
    temperature: 0
  depends_on:
    - fetch-data
```

#### Content Generation

```yaml
- id: generate-report
  type: claude_api
  config:
    model: claude-3-opus-20240229
    max_tokens: 4096
    system: |
      You are a business analyst. Generate professional reports.
      Use markdown formatting.
    prompt: |
      Generate a weekly status report based on this data:

      Completed tasks: {{ nodes.get-completed.output.body | tojson }}
      Open issues: {{ nodes.get-issues.output.body | tojson }}
      Metrics: {{ nodes.get-metrics.output.body | tojson }}
    temperature: 0.3
  depends_on:
    - get-completed
    - get-issues
    - get-metrics
```

## Output

Both Claude nodes output:

```json
{
  "response": "The generated text response...",
  "model": "claude-3-sonnet-20240229",
  "usage": {
    "input_tokens": 150,
    "output_tokens": 200
  }
}
```

Access in templates:
- `{{ nodes.my-claude.output.response }}`
- `{{ nodes.my-claude.output.usage.output_tokens }}`

## Error Handling

Claude nodes fail if:
- CLI is not installed (claude_cli)
- API key is invalid
- Rate limits are exceeded
- Request timeout

```yaml
- id: ai-task
  type: claude_api
  config:
    prompt: "{{ input.prompt }}"
  retry:
    max_attempts: 3
    delay_seconds: 10
    backoff_multiplier: 2

- id: fallback
  type: shell
  config:
    command: echo "AI processing unavailable"
  condition: "{{ nodes.ai-task.status == 'failed' }}"
```

## Best Practices

1. **Use appropriate models** - Sonnet for most tasks, Opus for complex reasoning
2. **Set temperature to 0** for deterministic outputs
3. **Use system prompts** to set consistent behavior
4. **Limit output with instructions** to avoid long responses
5. **Handle failures** with retries and fallbacks
6. **Monitor token usage** to manage costs
7. **Validate responses** before using in subsequent nodes

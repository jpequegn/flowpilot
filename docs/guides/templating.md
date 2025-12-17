# Templating

FlowPilot uses Jinja2-style templating for dynamic values in workflows.

## Basic Syntax

Template expressions are enclosed in `{{ }}`:

```yaml
- id: greet
  type: shell
  config:
    command: echo "Hello {{ input.name }}"
```

## Data Sources

### Input Data

Workflow input passed via CLI or API:

```yaml
command: echo "{{ input.message }}"
```

```bash
flowpilot run workflow --input '{"message": "Hello"}'
```

### Environment Variables

Access via the `env()` function:

```yaml
command: echo "User: {{ env('USER') }}"
url: "https://api.example.com?key={{ env('API_KEY') }}"
```

### Node Results

Access previous node outputs via `nodes.<id>`:

```yaml
# Previous node
- id: fetch
  type: http
  config:
    url: https://api.example.com/data

# Access its result
- id: process
  type: shell
  config:
    command: echo "Status: {{ nodes.fetch.output.status_code }}"
  depends_on:
    - fetch
```

**Available properties:**
- `nodes.<id>.status` - completed, failed, running, pending
- `nodes.<id>.output` - Node-specific output object
- `nodes.<id>.duration_ms` - Execution time
- `nodes.<id>.error` - Error message if failed

### Built-in Functions

#### now()

Current timestamp:

```yaml
message: "Generated at {{ now() }}"
path: "/logs/{{ now('%Y-%m-%d') }}.log"
```

Format strings (strftime):
- `%Y` - 4-digit year
- `%m` - 2-digit month
- `%d` - 2-digit day
- `%H` - 24-hour hour
- `%M` - Minutes
- `%S` - Seconds

---

## Filters

Filters transform values using the pipe `|` syntax.

### String Filters

```yaml
# Uppercase
message: "{{ input.name | upper }}"

# Lowercase
message: "{{ input.name | lower }}"

# Capitalize
message: "{{ input.name | capitalize }}"

# Trim whitespace
message: "{{ input.text | trim }}"

# Truncate
message: "{{ input.text | truncate(100) }}"

# Replace
message: "{{ input.path | replace('/', '-') }}"

# Default value
message: "{{ input.name | default('Anonymous') }}"
```

### List Filters

```yaml
# Length
count: "{{ items | length }}"

# First/Last
first: "{{ items | first }}"
last: "{{ items | last }}"

# Join
csv: "{{ items | join(', ') }}"

# Sort
sorted: "{{ items | sort }}"

# Reverse
reversed: "{{ items | reverse }}"

# Filter by attribute
active: "{{ items | selectattr('active', 'true') | list }}"

# Reject by attribute
inactive: "{{ items | rejectattr('active', 'true') | list }}"
```

### JSON Filters

```yaml
# Convert to JSON string
json_str: "{{ data | tojson }}"

# Parse JSON string
parsed: "{{ json_string | fromjson }}"
```

### Math Filters

```yaml
# Absolute value
abs_val: "{{ value | abs }}"

# Round
rounded: "{{ value | round(2) }}"

# Integer
integer: "{{ value | int }}"

# Float
decimal: "{{ value | float }}"
```

---

## Conditionals

### In Expressions

```yaml
message: "{{ 'Yes' if condition else 'No' }}"
```

### In Condition Nodes

```yaml
- id: check
  type: condition
  config:
    expression: "{{ input.enabled == true }}"
    then_branch: do-something
    else_branch: skip
```

### Skip Node Execution

```yaml
- id: optional-step
  type: shell
  config:
    command: echo "Only when enabled"
  condition: "{{ input.enabled }}"
```

---

## Operators

### Comparison

```yaml
# Equality
{{ a == b }}
{{ a != b }}

# Numeric
{{ a > b }}
{{ a < b }}
{{ a >= b }}
{{ a <= b }}

# Membership
{{ item in list }}
{{ item not in list }}
```

### Logical

```yaml
# AND
{{ a and b }}

# OR
{{ a or b }}

# NOT
{{ not a }}
```

### Arithmetic

```yaml
# Basic math
{{ a + b }}
{{ a - b }}
{{ a * b }}
{{ a / b }}
{{ a % b }}  # Modulo
```

---

## Complex Examples

### Chained Filters

```yaml
# Get first 5 active users, sorted by name
users: "{{ nodes.fetch.output.body.users | selectattr('active', 'true') | sort(attribute='name') | list | slice(0, 5) | list }}"
```

### Conditional Message

```yaml
message: |
  Status: {{ nodes.task.status }}
  {{ 'Duration: ' + (nodes.task.duration_ms | string) + 'ms' if nodes.task.status == 'completed' else 'Error: ' + nodes.task.error }}
```

### Dynamic URL

```yaml
url: "https://api.example.com/{{ input.version | default('v1') }}/{{ input.resource }}/{{ input.id }}"
```

### JSON Construction

```yaml
body:
  timestamp: "{{ now() }}"
  data: "{{ nodes.process.output | tojson }}"
  metadata:
    source: "{{ env('HOSTNAME') }}"
    workflow: "{{ workflow.name }}"
```

### Safe Navigation

Use `default` to handle missing values:

```yaml
# Safely access nested properties
value: "{{ nodes.api.output.body.data.items | default([]) | length }}"

# Default for missing input
name: "{{ input.user.name | default('Unknown') }}"
```

---

## Escaping

### Literal Braces

To output literal `{{` or `}}`:

```yaml
message: "Use {{ '{{' }} for templates"
# Output: Use {{ for templates
```

### Raw Blocks

For content that shouldn't be processed:

```yaml
command: |
  echo '{% raw %}{{ not a template }}{% endraw %}'
```

---

## Common Patterns

### Building File Paths

```yaml
path: "/data/{{ env('ENVIRONMENT') }}/{{ now('%Y/%m/%d') }}/output.json"
```

### Conditional Execution

```yaml
condition: "{{ nodes.check.output.stdout | trim == 'yes' }}"
```

### API Authentication

```yaml
headers:
  Authorization: "Bearer {{ env('API_TOKEN') }}"
```

### Data Transformation

```yaml
command: |
  echo '{{ nodes.fetch.output.body | tojson }}' | jq '.items | length'
```

### Error Handling

```yaml
condition: "{{ nodes.task.status == 'failed' }}"
message: "Error: {{ nodes.task.error | default('Unknown error') }}"
```

---

## Debugging Templates

Use the log node to inspect values:

```yaml
- id: debug
  type: log
  config:
    message: |
      Input: {{ input | tojson }}
      API Response: {{ nodes.api.output | tojson }}
    level: debug
```

---

## See Also

- [Workflow Syntax](workflow-syntax.md) - Complete YAML reference
- [Node Types](../nodes/) - Node-specific outputs
- [Examples](../examples/) - Real-world usage

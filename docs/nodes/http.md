# HTTP Node

Make HTTP requests to APIs and web services.

## Configuration

```yaml
- id: my-http-node
  type: http
  config:
    url: string           # Required: URL to request
    method: string        # Optional: HTTP method (default: GET)
    headers:              # Optional: HTTP headers
      Header-Name: value
    body: string|object   # Optional: request body
    timeout: integer      # Optional: timeout in seconds (default: 30)
    auth:                 # Optional: authentication
      type: basic|bearer
      username: string    # For basic auth
      password: string    # For basic auth
      token: string       # For bearer auth
```

## Examples

### GET Request

```yaml
- id: fetch-users
  type: http
  config:
    url: https://api.example.com/users
    method: GET
```

### POST with JSON Body

```yaml
- id: create-user
  type: http
  config:
    url: https://api.example.com/users
    method: POST
    headers:
      Content-Type: application/json
    body:
      name: John Doe
      email: john@example.com
```

### With Query Parameters

```yaml
- id: search
  type: http
  config:
    url: "https://api.example.com/search?q={{ input.query }}&limit=10"
    method: GET
```

### Bearer Token Authentication

```yaml
- id: authenticated-request
  type: http
  config:
    url: https://api.example.com/protected
    method: GET
    auth:
      type: bearer
      token: "{{ env('API_TOKEN') }}"
```

### Basic Authentication

```yaml
- id: basic-auth-request
  type: http
  config:
    url: https://api.example.com/protected
    method: GET
    auth:
      type: basic
      username: "{{ env('API_USER') }}"
      password: "{{ env('API_PASS') }}"
```

### PUT Request

```yaml
- id: update-resource
  type: http
  config:
    url: "https://api.example.com/users/{{ input.user_id }}"
    method: PUT
    headers:
      Content-Type: application/json
    body:
      name: "{{ input.new_name }}"
```

### DELETE Request

```yaml
- id: delete-resource
  type: http
  config:
    url: "https://api.example.com/users/{{ input.user_id }}"
    method: DELETE
```

### Custom Headers

```yaml
- id: with-headers
  type: http
  config:
    url: https://api.example.com/data
    method: GET
    headers:
      Authorization: "Bearer {{ env('TOKEN') }}"
      X-Custom-Header: my-value
      Accept: application/json
```

### With Timeout

```yaml
- id: slow-api
  type: http
  config:
    url: https://slow-api.example.com/process
    method: POST
    timeout: 120  # 2 minutes
    body:
      data: large-payload
```

## Output

The HTTP node outputs:

```json
{
  "status_code": 200,
  "headers": {
    "content-type": "application/json",
    "x-request-id": "abc123"
  },
  "body": {
    "id": 1,
    "name": "Response data"
  },
  "duration_ms": 250
}
```

Access in templates:
- `{{ nodes.my-node.output.status_code }}`
- `{{ nodes.my-node.output.body.id }}`
- `{{ nodes.my-node.output.headers['content-type'] }}`

## Error Handling

An HTTP node fails if:
- The request times out
- Network error occurs
- Status code indicates error (4xx, 5xx) by default

### Retry on Failure

```yaml
- id: flaky-api
  type: http
  config:
    url: https://api.example.com/data
  retry:
    max_attempts: 3
    delay_seconds: 5
    backoff_multiplier: 2
```

### Check Status Code

```yaml
- id: api-call
  type: http
  config:
    url: https://api.example.com/data

- id: handle-not-found
  type: shell
  config:
    command: echo "Resource not found"
  condition: "{{ nodes.api-call.output.status_code == 404 }}"
  depends_on:
    - api-call
```

## Chaining Requests

```yaml
- id: get-token
  type: http
  config:
    url: https://auth.example.com/token
    method: POST
    body:
      grant_type: client_credentials
      client_id: "{{ env('CLIENT_ID') }}"
      client_secret: "{{ env('CLIENT_SECRET') }}"

- id: use-token
  type: http
  config:
    url: https://api.example.com/protected
    method: GET
    headers:
      Authorization: "Bearer {{ nodes.get-token.output.body.access_token }}"
  depends_on:
    - get-token
```

## Best Practices

1. **Use environment variables** for API keys and secrets
2. **Set appropriate timeouts** for slow endpoints
3. **Implement retry logic** for unreliable APIs
4. **Log responses** for debugging
5. **Validate responses** before using in subsequent nodes

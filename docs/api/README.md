# API Reference

FlowPilot provides a REST API and WebSocket interface for programmatic access.

## Base URL

When running `flowpilot serve`, the API is available at:

```
http://localhost:8080/api/
```

## Authentication

Currently, FlowPilot does not require authentication. When exposing the API externally, use a reverse proxy with authentication.

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/workflows` | List all workflows |
| GET | `/api/workflows/{name}` | Get workflow details |
| POST | `/api/workflows/{name}/run` | Execute a workflow |
| GET | `/api/executions` | List executions |
| GET | `/api/executions/{id}` | Get execution details |
| GET | `/api/executions/{id}/logs` | Get execution logs |
| DELETE | `/api/executions/{id}` | Cancel execution |
| GET | `/api/health` | Health check |

---

## Workflows

### List Workflows

```http
GET /api/workflows
```

**Response:**

```json
{
  "workflows": [
    {
      "name": "example-workflow",
      "description": "An example workflow",
      "path": "/path/to/workflows/example.yaml",
      "triggers": [
        { "type": "manual" }
      ],
      "node_count": 3
    }
  ]
}
```

### Get Workflow Details

```http
GET /api/workflows/{name}
```

**Parameters:**
- `name` - Workflow name

**Response:**

```json
{
  "name": "example-workflow",
  "description": "An example workflow",
  "path": "/path/to/workflows/example.yaml",
  "triggers": [
    { "type": "manual" }
  ],
  "nodes": [
    {
      "id": "step1",
      "type": "shell",
      "config": {
        "command": "echo Hello"
      },
      "depends_on": []
    }
  ]
}
```

### Execute Workflow

```http
POST /api/workflows/{name}/run
```

**Parameters:**
- `name` - Workflow name

**Request Body:**

```json
{
  "input": {
    "key": "value"
  },
  "sync": false
}
```

- `input` (optional) - Input data for the workflow
- `sync` (optional) - Wait for completion (default: false)

**Response (async):**

```json
{
  "execution_id": "abc123",
  "status": "running",
  "workflow": "example-workflow",
  "started_at": "2024-01-15T10:30:00Z"
}
```

**Response (sync):**

```json
{
  "execution_id": "abc123",
  "status": "completed",
  "workflow": "example-workflow",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:05Z",
  "duration_ms": 5000,
  "node_results": {
    "step1": {
      "status": "completed",
      "output": {
        "stdout": "Hello"
      }
    }
  }
}
```

---

## Executions

### List Executions

```http
GET /api/executions
```

**Query Parameters:**
- `workflow` (optional) - Filter by workflow name
- `status` (optional) - Filter by status (pending, running, completed, failed)
- `limit` (optional) - Maximum results (default: 50)
- `offset` (optional) - Pagination offset

**Response:**

```json
{
  "executions": [
    {
      "id": "abc123",
      "workflow": "example-workflow",
      "status": "completed",
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:05Z",
      "duration_ms": 5000
    }
  ],
  "total": 100,
  "limit": 50,
  "offset": 0
}
```

### Get Execution Details

```http
GET /api/executions/{id}
```

**Parameters:**
- `id` - Execution ID

**Response:**

```json
{
  "id": "abc123",
  "workflow": "example-workflow",
  "status": "completed",
  "started_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:05Z",
  "duration_ms": 5000,
  "input": {
    "key": "value"
  },
  "node_results": {
    "step1": {
      "node_id": "step1",
      "status": "completed",
      "started_at": "2024-01-15T10:30:00Z",
      "completed_at": "2024-01-15T10:30:02Z",
      "duration_ms": 2000,
      "output": {
        "stdout": "Hello",
        "exit_code": 0
      }
    }
  }
}
```

### Get Execution Logs

```http
GET /api/executions/{id}/logs
```

**Parameters:**
- `id` - Execution ID

**Query Parameters:**
- `node` (optional) - Filter by node ID
- `level` (optional) - Filter by log level

**Response:**

```json
{
  "logs": [
    {
      "timestamp": "2024-01-15T10:30:00Z",
      "level": "info",
      "node_id": "step1",
      "message": "Starting execution"
    },
    {
      "timestamp": "2024-01-15T10:30:02Z",
      "level": "info",
      "node_id": "step1",
      "message": "Node completed"
    }
  ]
}
```

### Cancel Execution

```http
DELETE /api/executions/{id}
```

**Parameters:**
- `id` - Execution ID

**Response:**

```json
{
  "id": "abc123",
  "status": "cancelled",
  "message": "Execution cancelled"
}
```

---

## Health

### Health Check

```http
GET /api/health
```

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime": 3600
}
```

---

## WebSocket

Real-time updates are available via WebSocket.

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');
```

### Message Types

**Subscribe to execution:**

```json
{
  "type": "subscribe",
  "execution_id": "abc123"
}
```

**Execution update:**

```json
{
  "type": "execution_update",
  "execution_id": "abc123",
  "status": "running",
  "current_node": "step2"
}
```

**Node update:**

```json
{
  "type": "node_update",
  "execution_id": "abc123",
  "node_id": "step1",
  "status": "completed",
  "output": {
    "stdout": "Hello"
  }
}
```

**Log entry:**

```json
{
  "type": "log",
  "execution_id": "abc123",
  "node_id": "step1",
  "level": "info",
  "message": "Processing..."
}
```

---

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Workflow not found: unknown-workflow"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_ERROR` | 400 | Invalid request data |
| `EXECUTION_ERROR` | 500 | Workflow execution failed |
| `CONFLICT` | 409 | Resource conflict |

---

## Examples

### cURL

```bash
# List workflows
curl http://localhost:8080/api/workflows

# Run workflow
curl -X POST http://localhost:8080/api/workflows/example/run \
  -H "Content-Type: application/json" \
  -d '{"input": {"name": "World"}}'

# Get execution status
curl http://localhost:8080/api/executions/abc123
```

### Python

```python
import requests

# Run workflow
response = requests.post(
    "http://localhost:8080/api/workflows/example/run",
    json={"input": {"name": "World"}, "sync": True}
)
result = response.json()
print(f"Status: {result['status']}")
```

### JavaScript

```javascript
// Run workflow
const response = await fetch('http://localhost:8080/api/workflows/example/run', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ input: { name: 'World' } })
});
const result = await response.json();
console.log(`Execution ID: ${result.execution_id}`);
```

---

## See Also

- [CLI Reference](../cli/)
- [WebSocket Events](websocket.md)
- [Quick Start](../getting-started/quick-start.md)

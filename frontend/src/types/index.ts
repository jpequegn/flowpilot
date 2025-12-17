// Workflow types
export interface Workflow {
  name: string
  description?: string
  version: string
  nodes: WorkflowNode[]
  triggers?: WorkflowTrigger[]
  inputs?: WorkflowInput[]
}

export interface WorkflowNode {
  id: string
  type: string
  config: Record<string, unknown>
  depends_on?: string[]
}

export interface WorkflowTrigger {
  type: "schedule" | "webhook" | "manual"
  config: Record<string, unknown>
}

export interface WorkflowInput {
  name: string
  type: "string" | "number" | "boolean" | "object"
  required?: boolean
  default?: unknown
  description?: string
}

// Workflow list item (from API)
export interface WorkflowListItem {
  name: string
  description: string
  version: number
  path: string
  created_at: string | null
  updated_at: string | null
}

// Workflow detail (from API)
export interface WorkflowDetail {
  name: string
  description: string
  version: number
  path: string
  content: string
  triggers: Record<string, unknown>[]
  inputs: Record<string, unknown>
  node_count: number
  created_at: string | null
  updated_at: string | null
}

// Workflow create request
export interface WorkflowCreateRequest {
  name: string
  content: string
}

// Workflow update request
export interface WorkflowUpdateRequest {
  content: string
}

// Workflow validation response
export interface WorkflowValidation {
  valid: boolean
  errors: Record<string, unknown>[]
  warnings: string[]
}

// Workflow run request
export interface WorkflowRunRequest {
  inputs?: Record<string, unknown>
}

// Workflow run response
export interface WorkflowRunResponse {
  execution_id: string
  workflow: string
  status: string
}

// Execution types
export interface Execution {
  id: string
  workflow_name: string
  status: ExecutionStatusType
  started_at: string
  completed_at?: string
  inputs?: Record<string, unknown>
  outputs?: Record<string, unknown>
  error?: string
  nodes?: NodeExecution[]
}

export type ExecutionStatusType =
  | "pending"
  | "running"
  | "completed"
  | "failed"
  | "cancelled"

export interface NodeExecution {
  node_id: string
  status: ExecutionStatusType
  started_at?: string
  completed_at?: string
  outputs?: Record<string, unknown>
  error?: string
}

// Execution list item (from API)
export interface ExecutionListItem {
  id: string
  workflow_name: string
  status: ExecutionStatusType
  trigger_type: string | null
  started_at: string
  finished_at: string | null
  duration_ms: number | null
}

// Node execution response (from API)
export interface NodeExecutionResponse {
  id: number
  node_id: string
  node_type: string
  status: ExecutionStatusType
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  stdout: string
  stderr: string
  output: string
  error: string | null
}

// Execution detail (from API)
export interface ExecutionDetail {
  id: string
  workflow_name: string
  workflow_path: string
  status: ExecutionStatusType
  trigger_type: string | null
  inputs: Record<string, unknown>
  started_at: string
  finished_at: string | null
  duration_ms: number | null
  error: string | null
  node_executions: NodeExecutionResponse[]
}

// WebSocket message format
export interface WebSocketMessage {
  type: "log" | "status" | "error" | "heartbeat"
  execution_id: string
  timestamp: string
  data: Record<string, unknown>
}

// API response types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface ApiHealthResponse {
  status: string
  service?: string
}

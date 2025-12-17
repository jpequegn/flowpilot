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

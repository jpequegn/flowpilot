export const APP_NAME = "FlowPilot"
export const APP_VERSION = "0.1.0"

export const ROUTES = {
  HOME: "/",
  WORKFLOWS: "/workflows",
  WORKFLOW_DETAIL: "/workflows/:name",
  EXECUTIONS: "/executions",
  EXECUTION_DETAIL: "/executions/:id",
  SETTINGS: "/settings",
} as const

export const REFRESH_INTERVALS = {
  EXECUTIONS: 5000, // 5 seconds
  WORKFLOWS: 30000, // 30 seconds
} as const

export const EXECUTION_STATUS = {
  PENDING: "pending",
  RUNNING: "running",
  COMPLETED: "completed",
  FAILED: "failed",
  CANCELLED: "cancelled",
} as const

export type ExecutionStatus =
  (typeof EXECUTION_STATUS)[keyof typeof EXECUTION_STATUS]

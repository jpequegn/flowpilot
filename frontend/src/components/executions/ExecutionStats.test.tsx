import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { ExecutionStats } from "./ExecutionStats"
import type { ExecutionListItem } from "@/types"

describe("ExecutionStats", () => {
  it("renders all stats correctly", () => {
    const executions: ExecutionListItem[] = [
      {
        id: "1",
        workflow_name: "test",
        status: "completed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 1000,
      },
      {
        id: "2",
        workflow_name: "test",
        status: "completed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 2000,
      },
      {
        id: "3",
        workflow_name: "test",
        status: "failed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 500,
      },
      {
        id: "4",
        workflow_name: "test",
        status: "running",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: null,
        duration_ms: null,
      },
    ]

    render(<ExecutionStats executions={executions} />)

    // Total
    expect(screen.getByText("Total")).toBeInTheDocument()
    expect(screen.getByText("4")).toBeInTheDocument()

    // Completed
    expect(screen.getByText("Completed")).toBeInTheDocument()
    expect(screen.getByText("2")).toBeInTheDocument()

    // Failed
    expect(screen.getByText("Failed")).toBeInTheDocument()

    // Running (1 failed and 1 running both show "1", use getAllByText)
    expect(screen.getByText("Running")).toBeInTheDocument()
    expect(screen.getAllByText("1")).toHaveLength(2) // 1 failed + 1 running
  })

  it("calculates success rate correctly", () => {
    const executions: ExecutionListItem[] = [
      {
        id: "1",
        workflow_name: "test",
        status: "completed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 1000,
      },
      {
        id: "2",
        workflow_name: "test",
        status: "failed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 500,
      },
    ]

    render(<ExecutionStats executions={executions} />)

    // 1 completed out of 2 finished = 50%
    expect(screen.getByText("50%")).toBeInTheDocument()
  })

  it("calculates average duration correctly", () => {
    const executions: ExecutionListItem[] = [
      {
        id: "1",
        workflow_name: "test",
        status: "completed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 1000,
      },
      {
        id: "2",
        workflow_name: "test",
        status: "completed",
        trigger_type: "manual",
        started_at: "2024-01-01T00:00:00Z",
        finished_at: "2024-01-01T00:01:00Z",
        duration_ms: 3000,
      },
    ]

    render(<ExecutionStats executions={executions} />)

    // Average of 1000ms and 3000ms = 2000ms = 2s
    expect(screen.getByText("2.0s")).toBeInTheDocument()
  })

  it("handles empty executions", () => {
    render(<ExecutionStats executions={[]} />)

    expect(screen.getByText("Total")).toBeInTheDocument()
    expect(screen.getByText("0%")).toBeInTheDocument()
    expect(screen.getByText("-")).toBeInTheDocument() // No avg duration
  })
})

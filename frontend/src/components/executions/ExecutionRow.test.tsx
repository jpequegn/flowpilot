import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { BrowserRouter } from "react-router-dom"
import { ExecutionRow } from "./ExecutionRow"
import type { ExecutionListItem } from "@/types"

const wrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>
    <table>
      <tbody>{children}</tbody>
    </table>
  </BrowserRouter>
)

describe("ExecutionRow", () => {
  it("renders execution details", () => {
    const execution: ExecutionListItem = {
      id: "test-id-123",
      workflow_name: "my-workflow",
      status: "completed",
      trigger_type: "manual",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      duration_ms: 1500,
    }

    render(<ExecutionRow execution={execution} />, { wrapper })

    expect(screen.getByText("my-workflow")).toBeInTheDocument()
    expect(screen.getByText("completed")).toBeInTheDocument()
    expect(screen.getByText("manual")).toBeInTheDocument()
    expect(screen.getByText("1.5s")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: "View" })).toHaveAttribute(
      "href",
      "/executions/test-id-123"
    )
  })

  it("renders running status with spinner icon", () => {
    const execution: ExecutionListItem = {
      id: "test-id",
      workflow_name: "workflow",
      status: "running",
      trigger_type: "webhook",
      started_at: new Date().toISOString(),
      finished_at: null,
      duration_ms: null,
    }

    render(<ExecutionRow execution={execution} />, { wrapper })

    expect(screen.getByText("running")).toBeInTheDocument()
    // Duration should show - when null
    expect(screen.getByText("-")).toBeInTheDocument()
  })

  it("renders failed status", () => {
    const execution: ExecutionListItem = {
      id: "test-id",
      workflow_name: "workflow",
      status: "failed",
      trigger_type: "schedule",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      duration_ms: 500,
    }

    render(<ExecutionRow execution={execution} />, { wrapper })

    expect(screen.getByText("failed")).toBeInTheDocument()
    expect(screen.getByText("500ms")).toBeInTheDocument()
    expect(screen.getByText("schedule")).toBeInTheDocument()
  })

  it("links to workflow editor", () => {
    const execution: ExecutionListItem = {
      id: "test-id",
      workflow_name: "my-workflow",
      status: "completed",
      trigger_type: null,
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      duration_ms: 1000,
    }

    render(<ExecutionRow execution={execution} />, { wrapper })

    expect(screen.getByRole("link", { name: "my-workflow" })).toHaveAttribute(
      "href",
      "/workflows/my-workflow"
    )
  })

  it("shows - when trigger_type is null", () => {
    const execution: ExecutionListItem = {
      id: "test-id",
      workflow_name: "workflow",
      status: "completed",
      trigger_type: null,
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      duration_ms: 1000,
    }

    render(<ExecutionRow execution={execution} />, { wrapper })

    // The cell for trigger_type should show -
    const cells = screen.getAllByRole("cell")
    expect(cells[2]).toHaveTextContent("-")
  })

  it("formats duration in minutes for long executions", () => {
    const execution: ExecutionListItem = {
      id: "test-id",
      workflow_name: "workflow",
      status: "completed",
      trigger_type: "manual",
      started_at: new Date().toISOString(),
      finished_at: new Date().toISOString(),
      duration_ms: 120000, // 2 minutes
    }

    render(<ExecutionRow execution={execution} />, { wrapper })

    expect(screen.getByText("2.0m")).toBeInTheDocument()
  })
})

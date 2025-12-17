import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { BrowserRouter } from "react-router-dom"
import { WorkflowCard } from "./WorkflowCard"
import type { WorkflowListItem } from "@/types"

const mockWorkflow: WorkflowListItem = {
  name: "test-workflow",
  description: "A test workflow description",
  version: 1,
  path: "/workflows/test-workflow.yaml",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
}

const renderWithRouter = (ui: React.ReactElement) => {
  return render(<BrowserRouter>{ui}</BrowserRouter>)
}

describe("WorkflowCard", () => {
  it("renders workflow name and description", () => {
    renderWithRouter(<WorkflowCard workflow={mockWorkflow} />)

    expect(screen.getByText("test-workflow")).toBeInTheDocument()
    expect(screen.getByText("A test workflow description")).toBeInTheDocument()
  })

  it("renders version badge", () => {
    renderWithRouter(<WorkflowCard workflow={mockWorkflow} />)

    expect(screen.getByText("v1")).toBeInTheDocument()
  })

  it("shows 'No description' when description is empty", () => {
    const workflowNoDesc = { ...mockWorkflow, description: "" }
    renderWithRouter(<WorkflowCard workflow={workflowNoDesc} />)

    expect(screen.getByText("No description")).toBeInTheDocument()
  })

  it("renders relative time for updated_at", () => {
    renderWithRouter(<WorkflowCard workflow={mockWorkflow} />)

    // Should show "Updated X days ago" or similar
    expect(screen.getByText(/Updated/)).toBeInTheDocument()
  })

  it("links to workflow editor", () => {
    renderWithRouter(<WorkflowCard workflow={mockWorkflow} />)

    const link = screen.getByRole("link", { name: "test-workflow" })
    expect(link).toHaveAttribute("href", "/workflows/test-workflow")
  })

  it("calls onRun when Run Workflow is clicked", async () => {
    const user = userEvent.setup()
    const onRun = vi.fn()

    renderWithRouter(<WorkflowCard workflow={mockWorkflow} onRun={onRun} />)

    // Open dropdown menu
    const menuButton = screen.getByRole("button", { name: /open menu/i })
    await user.click(menuButton)

    // Click run
    const runItem = screen.getByRole("menuitem", { name: /run workflow/i })
    await user.click(runItem)

    expect(onRun).toHaveBeenCalledWith("test-workflow")
  })

  it("calls onDelete when Delete is clicked", async () => {
    const user = userEvent.setup()
    const onDelete = vi.fn()

    renderWithRouter(
      <WorkflowCard workflow={mockWorkflow} onDelete={onDelete} />
    )

    // Open dropdown menu
    const menuButton = screen.getByRole("button", { name: /open menu/i })
    await user.click(menuButton)

    // Click delete
    const deleteItem = screen.getByRole("menuitem", { name: /delete/i })
    await user.click(deleteItem)

    expect(onDelete).toHaveBeenCalledWith("test-workflow")
  })
})

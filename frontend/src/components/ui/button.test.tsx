import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import { Button } from "./button"

describe("Button", () => {
  it("renders with default variant", () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole("button")).toHaveTextContent("Click me")
  })

  it("renders with different variants", () => {
    const { rerender } = render(<Button variant="destructive">Delete</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()

    rerender(<Button variant="outline">Outline</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()

    rerender(<Button variant="secondary">Secondary</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()

    rerender(<Button variant="ghost">Ghost</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()

    rerender(<Button variant="link">Link</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()
  })

  it("renders with different sizes", () => {
    const { rerender } = render(<Button size="sm">Small</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()

    rerender(<Button size="lg">Large</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()

    rerender(<Button size="icon">Icon</Button>)
    expect(screen.getByRole("button")).toBeInTheDocument()
  })

  it("forwards ref correctly", () => {
    const ref = { current: null }
    render(<Button ref={ref}>With Ref</Button>)
    expect(ref.current).toBeInstanceOf(HTMLButtonElement)
  })

  it("can be disabled", () => {
    render(<Button disabled>Disabled</Button>)
    expect(screen.getByRole("button")).toBeDisabled()
  })
})

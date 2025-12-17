import { describe, it, expect, vi, beforeEach } from "vitest"
import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createElement } from "react"
import { useWorkflows, useWorkflow, workflowKeys } from "./useWorkflows"
import * as apiModule from "@/lib/api"

// Mock the api module
vi.mock("@/lib/api", () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  queryClient: new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  }),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })
  return ({ children }: { children: React.ReactNode }) =>
    createElement(QueryClientProvider, { client: queryClient }, children)
}

describe("useWorkflows", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetches workflows successfully", async () => {
    const mockWorkflows = [
      {
        name: "test-workflow",
        description: "Test description",
        version: 1,
        path: "/workflows/test.yaml",
        created_at: "2025-01-01T00:00:00Z",
        updated_at: "2025-01-01T00:00:00Z",
      },
    ]

    vi.mocked(apiModule.api.get).mockResolvedValueOnce(mockWorkflows)

    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockWorkflows)
    expect(apiModule.api.get).toHaveBeenCalledWith("/workflows?page=1")
  })

  it("fetches workflows with search parameter", async () => {
    const mockWorkflows = [
      {
        name: "search-result",
        description: "",
        version: 1,
        path: "/workflows/search-result.yaml",
        created_at: null,
        updated_at: null,
      },
    ]

    vi.mocked(apiModule.api.get).mockResolvedValueOnce(mockWorkflows)

    const { result } = renderHook(
      () => useWorkflows({ search: "search", page: 1 }),
      {
        wrapper: createWrapper(),
      }
    )

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(apiModule.api.get).toHaveBeenCalledWith(
      "/workflows?search=search&page=1"
    )
  })

  it("handles error states", async () => {
    vi.mocked(apiModule.api.get).mockRejectedValueOnce(new Error("API Error"))

    const { result } = renderHook(() => useWorkflows(), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })

    expect(result.current.error).toBeDefined()
  })
})

describe("useWorkflow", () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it("fetches a single workflow", async () => {
    const mockWorkflow = {
      name: "my-workflow",
      description: "My workflow description",
      version: 1,
      path: "/workflows/my-workflow.yaml",
      content: "name: my-workflow\n",
      triggers: [],
      inputs: {},
      node_count: 2,
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    }

    vi.mocked(apiModule.api.get).mockResolvedValueOnce(mockWorkflow)

    const { result } = renderHook(() => useWorkflow("my-workflow"), {
      wrapper: createWrapper(),
    })

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true)
    })

    expect(result.current.data).toEqual(mockWorkflow)
    expect(apiModule.api.get).toHaveBeenCalledWith("/workflows/my-workflow")
  })

  it("does not fetch when name is empty", () => {
    renderHook(() => useWorkflow(""), {
      wrapper: createWrapper(),
    })

    expect(apiModule.api.get).not.toHaveBeenCalled()
  })
})

describe("workflowKeys", () => {
  it("generates correct query keys", () => {
    expect(workflowKeys.all).toEqual(["workflows"])
    expect(workflowKeys.lists()).toEqual(["workflows", "list"])
    expect(workflowKeys.list({ search: "test" })).toEqual([
      "workflows",
      "list",
      { search: "test" },
    ])
    expect(workflowKeys.details()).toEqual(["workflows", "detail"])
    expect(workflowKeys.detail("my-workflow")).toEqual([
      "workflows",
      "detail",
      "my-workflow",
    ])
    expect(workflowKeys.validation("my-workflow")).toEqual([
      "workflows",
      "detail",
      "my-workflow",
      "validation",
    ])
  })
})

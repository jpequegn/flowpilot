import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type {
  WorkflowListItem,
  WorkflowDetail,
  WorkflowCreateRequest,
  WorkflowUpdateRequest,
  WorkflowValidation,
  WorkflowRunRequest,
  WorkflowRunResponse,
} from "@/types"

// Query keys
export const workflowKeys = {
  all: ["workflows"] as const,
  lists: () => [...workflowKeys.all, "list"] as const,
  list: (filters: { search?: string; page?: number }) =>
    [...workflowKeys.lists(), filters] as const,
  details: () => [...workflowKeys.all, "detail"] as const,
  detail: (name: string) => [...workflowKeys.details(), name] as const,
  validation: (name: string) =>
    [...workflowKeys.detail(name), "validation"] as const,
}

// Fetch all workflows
export function useWorkflows(options?: { search?: string; page?: number }) {
  const { search, page = 1 } = options ?? {}

  return useQuery({
    queryKey: workflowKeys.list({ search, page }),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (search) params.set("search", search)
      params.set("page", String(page))
      const queryString = params.toString()
      return api.get<WorkflowListItem[]>(
        `/workflows${queryString ? `?${queryString}` : ""}`
      )
    },
  })
}

// Fetch single workflow
export function useWorkflow(name: string) {
  return useQuery({
    queryKey: workflowKeys.detail(name),
    queryFn: () =>
      api.get<WorkflowDetail>(`/workflows/${encodeURIComponent(name)}`),
    enabled: !!name,
  })
}

// Validate workflow
export function useWorkflowValidation(name: string) {
  return useQuery({
    queryKey: workflowKeys.validation(name),
    queryFn: () =>
      api.get<WorkflowValidation>(
        `/workflows/${encodeURIComponent(name)}/validate`
      ),
    enabled: !!name,
  })
}

// Create workflow mutation
export function useCreateWorkflow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: WorkflowCreateRequest) =>
      api.post<WorkflowDetail>("/workflows", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
    },
  })
}

// Update workflow mutation
export function useUpdateWorkflow(name: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: WorkflowUpdateRequest) =>
      api.put<WorkflowDetail>(`/workflows/${encodeURIComponent(name)}`, data),
    onSuccess: (data) => {
      queryClient.setQueryData(workflowKeys.detail(name), data)
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
    },
  })
}

// Delete workflow mutation
export function useDeleteWorkflow() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (name: string) =>
      api.delete<void>(`/workflows/${encodeURIComponent(name)}`),
    onSuccess: (_, name) => {
      queryClient.removeQueries({ queryKey: workflowKeys.detail(name) })
      queryClient.invalidateQueries({ queryKey: workflowKeys.lists() })
    },
  })
}

// Run workflow mutation
export function useRunWorkflow(name: string) {
  return useMutation({
    mutationFn: (data?: WorkflowRunRequest) =>
      api.post<WorkflowRunResponse>(
        `/workflows/${encodeURIComponent(name)}/run`,
        data ?? {}
      ),
  })
}

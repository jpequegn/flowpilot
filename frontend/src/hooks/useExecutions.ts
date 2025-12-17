import { useQuery } from "@tanstack/react-query"
import { useEffect, useState, useCallback, useRef } from "react"
import { api } from "@/lib/api"
import type {
  ExecutionListItem,
  ExecutionDetail,
  WebSocketMessage,
  NodeExecutionResponse,
} from "@/types"

// Query keys
export const executionKeys = {
  all: ["executions"] as const,
  lists: () => [...executionKeys.all, "list"] as const,
  list: (filters: { workflow?: string; status?: string }) =>
    [...executionKeys.lists(), filters] as const,
  details: () => [...executionKeys.all, "detail"] as const,
  detail: (id: string) => [...executionKeys.details(), id] as const,
}

// Fetch all executions
export function useExecutions(options?: {
  workflow?: string
  status?: string
}) {
  const { workflow, status } = options ?? {}

  return useQuery({
    queryKey: executionKeys.list({ workflow, status }),
    queryFn: async () => {
      const params = new URLSearchParams()
      if (workflow) params.set("workflow", workflow)
      if (status) params.set("status", status)
      const queryString = params.toString()
      return api.get<ExecutionListItem[]>(
        `/executions${queryString ? `?${queryString}` : ""}`
      )
    },
  })
}

// Fetch single execution
export function useExecution(id: string) {
  return useQuery({
    queryKey: executionKeys.detail(id),
    queryFn: () => api.get<ExecutionDetail>(`/executions/${id}`),
    enabled: !!id,
    // Refetch more frequently for running executions
    refetchInterval: (query) => {
      const data = query.state.data
      if (data?.status === "running" || data?.status === "pending") {
        return 2000 // Refetch every 2 seconds
      }
      return false
    },
  })
}

// WebSocket hook for live execution updates
export function useLiveExecutionUpdates(executionId: string | null) {
  const [nodeResults, setNodeResults] = useState<
    Record<string, NodeExecutionResponse>
  >({})
  const [isConnected, setIsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    if (!executionId) return

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
    const wsUrl = `${protocol}//${window.location.host}/api/executions/${executionId}/ws`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setIsConnected(true)
      }

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data)

          if (message.type === "log" && message.data.node_execution) {
            const nodeExec = message.data
              .node_execution as NodeExecutionResponse
            setNodeResults((prev) => ({
              ...prev,
              [nodeExec.node_id]: nodeExec,
            }))
          }
        } catch (e) {
          console.error("Failed to parse WebSocket message:", e)
        }
      }

      ws.onclose = () => {
        setIsConnected(false)
      }

      ws.onerror = (error) => {
        console.error("WebSocket error:", error)
        setIsConnected(false)
      }
    } catch (e) {
      console.error("Failed to create WebSocket:", e)
    }
  }, [executionId])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { nodeResults, isConnected }
}

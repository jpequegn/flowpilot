import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  AlertCircle,
} from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { ExecutionStatusType } from "@/types"
import type { NodeResult } from "@/lib/flowParser"

interface ExecutionSidebarProps {
  executionId: string
  workflowName: string
  status: ExecutionStatusType
  startedAt?: string
  completedAt?: string
  nodeResults: Record<string, NodeResult>
  selectedNodeId?: string | null
  onNodeSelect?: (nodeId: string) => void
}

const statusConfig: Record<
  ExecutionStatusType,
  { icon: typeof CheckCircle2; color: string; bgColor: string }
> = {
  pending: {
    icon: Clock,
    color: "text-slate-500",
    bgColor: "bg-slate-100",
  },
  running: {
    icon: Loader2,
    color: "text-blue-500",
    bgColor: "bg-blue-100",
  },
  completed: {
    icon: CheckCircle2,
    color: "text-green-500",
    bgColor: "bg-green-100",
  },
  failed: {
    icon: XCircle,
    color: "text-red-500",
    bgColor: "bg-red-100",
  },
  cancelled: {
    icon: AlertCircle,
    color: "text-yellow-500",
    bgColor: "bg-yellow-100",
  },
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString()
}

export function ExecutionSidebar({
  executionId,
  workflowName,
  status,
  startedAt,
  completedAt,
  nodeResults,
  selectedNodeId,
  onNodeSelect,
}: ExecutionSidebarProps) {
  const StatusIcon = statusConfig[status].icon
  const sortedNodes = Object.entries(nodeResults).sort(([, a], [, b]) => {
    if (!a.started_at) return 1
    if (!b.started_at) return -1
    return new Date(a.started_at).getTime() - new Date(b.started_at).getTime()
  })

  const totalDuration =
    startedAt && completedAt
      ? new Date(completedAt).getTime() - new Date(startedAt).getTime()
      : undefined

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-4 border-b">
        <h3 className="font-semibold text-lg">{workflowName}</h3>
        <p className="text-xs text-muted-foreground truncate">
          {executionId.slice(0, 8)}...
        </p>

        <div className="mt-3 flex items-center gap-2">
          <Badge
            variant={status === "failed" ? "destructive" : "outline"}
            className={cn(
              "gap-1",
              statusConfig[status].bgColor,
              statusConfig[status].color
            )}
          >
            <StatusIcon
              className={cn("w-3 h-3", status === "running" && "animate-spin")}
            />
            {status}
          </Badge>
          {totalDuration !== undefined && (
            <span className="text-xs text-muted-foreground">
              {formatDuration(totalDuration)}
            </span>
          )}
        </div>

        {startedAt && (
          <div className="mt-2 text-xs text-muted-foreground">
            Started: {formatTime(startedAt)}
          </div>
        )}
      </div>

      {/* Node List */}
      <div className="flex-1 overflow-auto p-2">
        <h4 className="text-sm font-medium px-2 py-1 text-muted-foreground">
          Nodes ({sortedNodes.length})
        </h4>
        <div className="space-y-1">
          {sortedNodes.map(([nodeId, result]) => {
            const NodeStatusIcon = statusConfig[result.status]?.icon || Clock
            const isSelected = selectedNodeId === nodeId

            return (
              <button
                key={nodeId}
                onClick={() => onNodeSelect?.(nodeId)}
                className={cn(
                  "w-full flex items-center gap-2 p-2 rounded-md text-left transition-colors",
                  "hover:bg-accent",
                  isSelected && "bg-accent"
                )}
              >
                <NodeStatusIcon
                  className={cn(
                    "w-4 h-4 flex-shrink-0",
                    statusConfig[result.status]?.color || "text-slate-500",
                    result.status === "running" && "animate-spin"
                  )}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{nodeId}</div>
                  {result.duration_ms !== undefined && (
                    <div className="text-xs text-muted-foreground">
                      {formatDuration(result.duration_ms)}
                    </div>
                  )}
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* Selected Node Details */}
      {selectedNodeId && nodeResults[selectedNodeId] && (
        <div className="border-t p-4">
          <h4 className="text-sm font-medium mb-2">Node Details</h4>
          <div className="text-xs space-y-1">
            <div>
              <span className="text-muted-foreground">ID:</span>{" "}
              {selectedNodeId}
            </div>
            <div>
              <span className="text-muted-foreground">Status:</span>{" "}
              {nodeResults[selectedNodeId].status}
            </div>
            {nodeResults[selectedNodeId].duration_ms !== undefined && (
              <div>
                <span className="text-muted-foreground">Duration:</span>{" "}
                {formatDuration(nodeResults[selectedNodeId].duration_ms!)}
              </div>
            )}
            {nodeResults[selectedNodeId].error && (
              <div className="mt-2 p-2 bg-red-50 rounded text-red-700">
                {nodeResults[selectedNodeId].error}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

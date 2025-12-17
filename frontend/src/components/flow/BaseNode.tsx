import { Handle, Position } from "@xyflow/react"
import { cn } from "@/lib/utils"
import type { ExecutionStatusType } from "@/types"
import type { ReactNode } from "react"

interface BaseNodeProps {
  label: string
  status?: ExecutionStatusType
  duration_ms?: number
  error?: string
  selected?: boolean
  icon: ReactNode
  iconColor: string
  children?: ReactNode
}

const statusStyles: Record<ExecutionStatusType | "default", string> = {
  pending: "border-slate-300 bg-white",
  running: "border-blue-500 bg-blue-50 animate-pulse",
  completed: "border-green-500 bg-green-50",
  failed: "border-red-500 bg-red-50",
  cancelled: "border-yellow-500 bg-yellow-50",
  default: "border-slate-300 bg-white",
}

export function BaseNode({
  label,
  status,
  duration_ms,
  error,
  selected,
  icon,
  iconColor,
  children,
}: BaseNodeProps) {
  const statusStyle = statusStyles[status ?? "default"]

  return (
    <div
      className={cn(
        "px-4 py-3 rounded-lg shadow-md border-2 min-w-[180px] max-w-[240px]",
        statusStyle,
        selected && "ring-2 ring-primary ring-offset-2"
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-slate-400 !w-3 !h-3"
      />

      <div className="flex items-center gap-2">
        <div className={cn("flex-shrink-0", iconColor)}>{icon}</div>
        <span className="font-medium text-sm truncate">{label}</span>
      </div>

      {children}

      {duration_ms !== undefined && (
        <div className="mt-1 text-xs text-muted-foreground">
          {duration_ms < 1000
            ? `${duration_ms}ms`
            : `${(duration_ms / 1000).toFixed(2)}s`}
        </div>
      )}

      {error && (
        <div className="mt-1 text-xs text-red-600 truncate" title={error}>
          {error}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-slate-400 !w-3 !h-3"
      />
    </div>
  )
}

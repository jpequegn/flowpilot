import { Link } from "react-router-dom"
import { CheckCircle, XCircle, Loader2, Clock, Ban } from "lucide-react"
import { formatDistanceToNow } from "date-fns"
import { TableCell, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import type { ExecutionListItem, ExecutionStatusType } from "@/types"
import { cn } from "@/lib/utils"

interface ExecutionRowProps {
  execution: ExecutionListItem
}

const statusConfig: Record<
  ExecutionStatusType,
  {
    icon: React.ReactNode
    color: string
    bgColor: string
  }
> = {
  completed: {
    icon: <CheckCircle className="h-4 w-4" />,
    color: "text-green-600",
    bgColor: "bg-green-50",
  },
  failed: {
    icon: <XCircle className="h-4 w-4" />,
    color: "text-red-600",
    bgColor: "bg-red-50",
  },
  running: {
    icon: <Loader2 className="h-4 w-4 animate-spin" />,
    color: "text-blue-600",
    bgColor: "bg-blue-50",
  },
  pending: {
    icon: <Clock className="h-4 w-4" />,
    color: "text-gray-500",
    bgColor: "bg-gray-50",
  },
  cancelled: {
    icon: <Ban className="h-4 w-4" />,
    color: "text-yellow-600",
    bgColor: "bg-yellow-50",
  },
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}m`
}

export function ExecutionRow({ execution }: ExecutionRowProps) {
  const config = statusConfig[execution.status]

  return (
    <TableRow className="hover:bg-muted/50">
      <TableCell>
        <Link
          to={`/workflows/${execution.workflow_name}`}
          className="font-medium hover:underline"
        >
          {execution.workflow_name}
        </Link>
      </TableCell>
      <TableCell>
        <div
          className={cn(
            "flex items-center gap-2 w-fit px-2 py-1 rounded-full",
            config.bgColor
          )}
        >
          <span className={config.color}>{config.icon}</span>
          <span className={cn("capitalize text-sm", config.color)}>
            {execution.status}
          </span>
        </div>
      </TableCell>
      <TableCell>
        {execution.trigger_type ? (
          <Badge variant="outline">{execution.trigger_type}</Badge>
        ) : (
          <span className="text-muted-foreground">-</span>
        )}
      </TableCell>
      <TableCell>
        <span title={execution.started_at}>
          {formatDistanceToNow(new Date(execution.started_at))} ago
        </span>
      </TableCell>
      <TableCell>
        {execution.duration_ms ? formatDuration(execution.duration_ms) : "-"}
      </TableCell>
      <TableCell>
        <Button size="sm" variant="ghost" asChild>
          <Link to={`/executions/${execution.id}`}>View</Link>
        </Button>
      </TableCell>
    </TableRow>
  )
}

import { useMemo } from "react"
import {
  CheckCircle,
  XCircle,
  Loader2,
  Clock,
  TrendingUp,
  Activity,
} from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import type { ExecutionListItem } from "@/types"

interface ExecutionStatsProps {
  executions: ExecutionListItem[]
}

export function ExecutionStats({ executions }: ExecutionStatsProps) {
  const stats = useMemo(() => {
    const total = executions.length
    const completed = executions.filter((e) => e.status === "completed").length
    const failed = executions.filter((e) => e.status === "failed").length
    const running = executions.filter((e) => e.status === "running").length
    const pending = executions.filter((e) => e.status === "pending").length

    // Calculate success rate
    const finishedCount = completed + failed
    const successRate =
      finishedCount > 0 ? (completed / finishedCount) * 100 : 0

    // Calculate average duration (only for completed executions with duration)
    const completedWithDuration = executions.filter(
      (e) => e.status === "completed" && e.duration_ms
    )
    const avgDuration =
      completedWithDuration.length > 0
        ? completedWithDuration.reduce(
            (sum, e) => sum + (e.duration_ms ?? 0),
            0
          ) / completedWithDuration.length
        : 0

    return {
      total,
      completed,
      failed,
      running,
      pending,
      successRate,
      avgDuration,
    }
  }, [executions])

  const formatDuration = (ms: number): string => {
    if (ms === 0) return "-"
    if (ms < 1000) return `${Math.round(ms)}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${(ms / 60000).toFixed(1)}m`
  }

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total</p>
              <p className="text-2xl font-bold">{stats.total}</p>
            </div>
            <Activity className="h-8 w-8 text-muted-foreground/50" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Completed</p>
              <p className="text-2xl font-bold text-green-600">
                {stats.completed}
              </p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-500/50" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Failed</p>
              <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
            </div>
            <XCircle className="h-8 w-8 text-red-500/50" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Running</p>
              <p className="text-2xl font-bold text-blue-600">
                {stats.running}
              </p>
            </div>
            <Loader2 className="h-8 w-8 text-blue-500/50 animate-spin" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Success Rate</p>
              <p className="text-2xl font-bold">
                {stats.successRate.toFixed(0)}%
              </p>
            </div>
            <TrendingUp className="h-8 w-8 text-muted-foreground/50" />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Avg Duration</p>
              <p className="text-2xl font-bold">
                {formatDuration(stats.avgDuration)}
              </p>
            </div>
            <Clock className="h-8 w-8 text-muted-foreground/50" />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

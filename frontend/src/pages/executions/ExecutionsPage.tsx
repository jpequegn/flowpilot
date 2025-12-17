import { useState } from "react"
import { Loader2, History } from "lucide-react"
import {
  Table,
  TableBody,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  ExecutionFilters,
  ExecutionRow,
  ExecutionStats,
  type ExecutionFiltersValue,
} from "@/components/executions"
import { useExecutions } from "@/hooks/useExecutions"
import { useWorkflows } from "@/hooks/useWorkflows"
import type { ExecutionStatusType } from "@/types"

export function ExecutionsPage() {
  const [filters, setFilters] = useState<ExecutionFiltersValue>({})

  // Fetch executions with filters
  const {
    data: executions,
    isLoading: execLoading,
    error: execError,
  } = useExecutions({
    workflow: filters.workflow,
    status: filters.status as ExecutionStatusType | undefined,
  })

  // Fetch workflows for filter dropdown
  const { data: workflows } = useWorkflows()
  const workflowNames = workflows?.map((w) => w.name) ?? []

  if (execLoading) {
    return (
      <div className="flex h-[calc(100vh-8rem)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (execError) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Executions</h1>
          <p className="text-muted-foreground">
            View and monitor workflow execution history.
          </p>
        </div>
        <div className="rounded-lg border bg-destructive/10 p-8 text-center">
          <h2 className="text-lg font-semibold text-destructive">
            Failed to load executions
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Please try again later.
          </p>
        </div>
      </div>
    )
  }

  const hasExecutions = executions && executions.length > 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Executions</h1>
          <p className="text-muted-foreground">
            View and monitor workflow execution history.
          </p>
        </div>
      </div>

      {hasExecutions && <ExecutionStats executions={executions} />}

      <ExecutionFilters
        value={filters}
        onChange={setFilters}
        workflows={workflowNames}
      />

      {hasExecutions ? (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Workflow</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Trigger</TableHead>
                <TableHead>Started</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {executions.map((execution) => (
                <ExecutionRow key={execution.id} execution={execution} />
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="rounded-lg border bg-card p-8 text-center">
          <History className="mx-auto h-12 w-12 text-muted-foreground/50" />
          <h2 className="mt-4 text-lg font-semibold">No executions found</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {filters.workflow || filters.status
              ? "No executions match your current filters."
              : "Run a workflow to see execution history here."}
          </p>
        </div>
      )}
    </div>
  )
}

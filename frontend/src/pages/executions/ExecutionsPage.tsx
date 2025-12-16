export function ExecutionsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Executions</h1>
        <p className="text-muted-foreground">
          View and monitor workflow execution history.
        </p>
      </div>

      <div className="rounded-lg border bg-card p-8 text-center">
        <h2 className="text-lg font-semibold">No executions yet</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Run a workflow to see execution history here.
        </p>
      </div>
    </div>
  )
}

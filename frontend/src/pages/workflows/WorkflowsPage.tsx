import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"

export function WorkflowsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">
            Create and manage your automation workflows.
          </p>
        </div>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          New Workflow
        </Button>
      </div>

      <div className="rounded-lg border bg-card p-8 text-center">
        <h2 className="text-lg font-semibold">No workflows yet</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Create your first workflow to automate your tasks.
        </p>
        <Button className="mt-4">
          <Plus className="mr-2 h-4 w-4" />
          Create Workflow
        </Button>
      </div>
    </div>
  )
}

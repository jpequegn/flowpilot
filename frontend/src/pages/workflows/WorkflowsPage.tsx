import { useState } from "react"
import { Plus, Search, Loader2, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { WorkflowCard } from "@/components/workflows/WorkflowCard"
import { NewWorkflowDialog } from "@/components/workflows/NewWorkflowDialog"
import { DeleteWorkflowDialog } from "@/components/workflows/DeleteWorkflowDialog"
import {
  useWorkflows,
  useDeleteWorkflow,
  useRunWorkflow,
} from "@/hooks/useWorkflows"
import { useDebounceValue } from "usehooks-ts"

export function WorkflowsPage() {
  const [search, setSearch] = useState("")
  const [isNewDialogOpen, setIsNewDialogOpen] = useState(false)
  const [workflowToDelete, setWorkflowToDelete] = useState<string | null>(null)
  const [workflowToRun, setWorkflowToRun] = useState<string | null>(null)

  const [debouncedSearch] = useDebounceValue(search, 300)
  const {
    data: workflows,
    isLoading,
    error,
  } = useWorkflows({
    search: debouncedSearch || undefined,
  })
  const deleteWorkflow = useDeleteWorkflow()
  const runWorkflow = useRunWorkflow(workflowToRun ?? "")

  const handleDelete = async () => {
    if (!workflowToDelete) return
    try {
      await deleteWorkflow.mutateAsync(workflowToDelete)
      setWorkflowToDelete(null)
    } catch {
      // Error handled by mutation
    }
  }

  const handleRun = async (name: string) => {
    setWorkflowToRun(name)
    try {
      await runWorkflow.mutateAsync({})
    } catch {
      // Error handled by mutation
    } finally {
      setWorkflowToRun(null)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Workflows</h1>
          <p className="text-muted-foreground">
            Create and manage your automation workflows.
          </p>
        </div>
        <Button onClick={() => setIsNewDialogOpen(true)}>
          <Plus className="mr-2 h-4 w-4" />
          New Workflow
        </Button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="Search workflows..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-9"
        />
      </div>

      {/* Error State */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            Failed to load workflows. Please try again.
          </AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && workflows?.length === 0 && (
        <div className="rounded-lg border bg-card p-8 text-center">
          <h2 className="text-lg font-semibold">
            {search ? "No workflows found" : "No workflows yet"}
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            {search
              ? "Try adjusting your search terms."
              : "Create your first workflow to automate your tasks."}
          </p>
          {!search && (
            <Button className="mt-4" onClick={() => setIsNewDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Create Workflow
            </Button>
          )}
        </div>
      )}

      {/* Workflow Grid */}
      {!isLoading && !error && workflows && workflows.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {workflows.map((workflow) => (
            <WorkflowCard
              key={workflow.name}
              workflow={workflow}
              onRun={handleRun}
              onDelete={setWorkflowToDelete}
            />
          ))}
        </div>
      )}

      {/* New Workflow Dialog */}
      <NewWorkflowDialog
        open={isNewDialogOpen}
        onOpenChange={setIsNewDialogOpen}
      />

      {/* Delete Confirmation Dialog */}
      <DeleteWorkflowDialog
        workflowName={workflowToDelete}
        open={!!workflowToDelete}
        onOpenChange={(open) => !open && setWorkflowToDelete(null)}
        onConfirm={handleDelete}
        isDeleting={deleteWorkflow.isPending}
      />
    </div>
  )
}

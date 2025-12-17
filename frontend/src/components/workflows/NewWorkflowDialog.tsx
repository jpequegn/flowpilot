import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2 } from "lucide-react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { useCreateWorkflow } from "@/hooks/useWorkflows"

interface NewWorkflowDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const DEFAULT_WORKFLOW_CONTENT = `name: my-workflow
description: A new workflow
version: 1

nodes:
  - id: start
    type: log
    config:
      message: "Hello, World!"
`

export function NewWorkflowDialog({
  open,
  onOpenChange,
}: NewWorkflowDialogProps) {
  const navigate = useNavigate()
  const createWorkflow = useCreateWorkflow()
  const [name, setName] = useState("")
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (!name.trim()) {
      setError("Workflow name is required")
      return
    }

    // Validate name format
    if (!/^[a-z][a-z0-9-]*$/.test(name)) {
      setError(
        "Name must start with a lowercase letter and contain only lowercase letters, numbers, and hyphens"
      )
      return
    }

    try {
      const content = DEFAULT_WORKFLOW_CONTENT.replace("my-workflow", name)
      await createWorkflow.mutateAsync({ name, content })
      onOpenChange(false)
      setName("")
      navigate(`/workflows/${encodeURIComponent(name)}`)
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message)
      } else {
        setError("Failed to create workflow")
      }
    }
  }

  const handleOpenChange = (open: boolean) => {
    if (!open) {
      setName("")
      setError(null)
    }
    onOpenChange(open)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Create New Workflow</DialogTitle>
            <DialogDescription>
              Enter a name for your new workflow. You can edit the YAML
              configuration after creation.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            <div className="space-y-2">
              <label
                htmlFor="workflow-name"
                className="text-sm font-medium leading-none"
              >
                Workflow Name
              </label>
              <Input
                id="workflow-name"
                placeholder="my-workflow"
                value={name}
                onChange={(e) => setName(e.target.value.toLowerCase())}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                Lowercase letters, numbers, and hyphens only.
              </p>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => handleOpenChange(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={createWorkflow.isPending}>
              {createWorkflow.isPending && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Create Workflow
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

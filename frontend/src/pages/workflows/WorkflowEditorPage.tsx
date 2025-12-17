import { useEffect, useState, useCallback } from "react"
import { useParams, useNavigate, Link } from "react-router-dom"
import Editor from "@monaco-editor/react"
import {
  ArrowLeft,
  Save,
  Play,
  Loader2,
  AlertCircle,
  CheckCircle2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import {
  useWorkflow,
  useUpdateWorkflow,
  useRunWorkflow,
} from "@/hooks/useWorkflows"
import { useDebounceValue } from "usehooks-ts"

export function WorkflowEditorPage() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const decodedName = name ? decodeURIComponent(name) : ""

  const { data: workflow, isLoading, error } = useWorkflow(decodedName)
  const updateWorkflow = useUpdateWorkflow(decodedName)
  const runWorkflow = useRunWorkflow(decodedName)

  const [content, setContent] = useState("")
  const [hasChanges, setHasChanges] = useState(false)
  const [saveStatus, setSaveStatus] = useState<
    "idle" | "saving" | "saved" | "error"
  >("idle")

  // Initialize content when workflow loads
  useEffect(() => {
    if (workflow?.content) {
      setContent(workflow.content)
      setHasChanges(false)
    }
  }, [workflow?.content])

  // Debounced content for auto-save
  const [debouncedContent] = useDebounceValue(content, 1000)

  // Auto-save when content changes
  useEffect(() => {
    if (
      debouncedContent &&
      workflow?.content &&
      debouncedContent !== workflow.content &&
      hasChanges
    ) {
      handleSave()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedContent])

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setContent(value)
      setHasChanges(value !== workflow?.content)
      setSaveStatus("idle")
    }
  }

  const handleSave = useCallback(async () => {
    if (!hasChanges) return

    setSaveStatus("saving")
    try {
      await updateWorkflow.mutateAsync({ content })
      setHasChanges(false)
      setSaveStatus("saved")
      setTimeout(() => setSaveStatus("idle"), 2000)
    } catch {
      setSaveStatus("error")
    }
  }, [content, hasChanges, updateWorkflow])

  const handleRun = async () => {
    try {
      const result = await runWorkflow.mutateAsync({})
      navigate(`/executions/${result.execution_id}`)
    } catch {
      // Error handled by mutation
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault()
        handleSave()
      }
    }

    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleSave])

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-8rem)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (error || !workflow) {
    return (
      <div className="space-y-4">
        <Link
          to="/workflows"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Workflows
        </Link>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {error
              ? "Failed to load workflow. Please try again."
              : "Workflow not found."}
          </AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-4">
        <div className="flex items-center gap-4">
          <Link
            to="/workflows"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {workflow.name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {workflow.description || "No description"}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {/* Save Status */}
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            {saveStatus === "saving" && (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Saving...</span>
              </>
            )}
            {saveStatus === "saved" && (
              <>
                <CheckCircle2 className="h-4 w-4 text-green-500" />
                <span className="text-green-500">Saved</span>
              </>
            )}
            {saveStatus === "error" && (
              <>
                <AlertCircle className="h-4 w-4 text-destructive" />
                <span className="text-destructive">Save failed</span>
              </>
            )}
            {saveStatus === "idle" && hasChanges && (
              <Badge variant="outline">Unsaved changes</Badge>
            )}
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleSave}
            disabled={!hasChanges || updateWorkflow.isPending}
          >
            <Save className="mr-2 h-4 w-4" />
            Save
          </Button>

          <Button
            size="sm"
            onClick={handleRun}
            disabled={runWorkflow.isPending}
          >
            {runWorkflow.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Play className="mr-2 h-4 w-4" />
            )}
            Run
          </Button>
        </div>
      </div>

      {/* Editor */}
      <div className="flex-1 overflow-hidden rounded-lg border mt-4">
        <Editor
          height="100%"
          defaultLanguage="yaml"
          value={content}
          onChange={handleEditorChange}
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 14,
            lineNumbers: "on",
            scrollBeyondLastLine: false,
            wordWrap: "on",
            tabSize: 2,
            insertSpaces: true,
            automaticLayout: true,
            padding: { top: 16, bottom: 16 },
          }}
        />
      </div>
    </div>
  )
}

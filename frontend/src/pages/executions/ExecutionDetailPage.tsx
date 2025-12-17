import { useState, useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import {
  ArrowLeft,
  Loader2,
  AlertCircle,
  GitBranch,
  ScrollText,
} from "lucide-react"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { FlowCanvas, ExecutionSidebar } from "@/components/flow"
import { LiveLogViewer } from "@/components/executions"
import { useExecution, useLiveExecutionUpdates } from "@/hooks/useExecutions"
import { useWorkflow } from "@/hooks/useWorkflows"
import { extractNodesFromYaml } from "@/lib/yamlParser"
import type { NodeResult } from "@/lib/flowParser"

export function ExecutionDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<string>("flow")

  const {
    data: execution,
    isLoading: execLoading,
    error: execError,
  } = useExecution(id ?? "")
  const { data: workflow, isLoading: workflowLoading } = useWorkflow(
    execution?.workflow_name ?? ""
  )

  // Live updates via WebSocket
  const { nodeResults: liveResults, isConnected } = useLiveExecutionUpdates(
    execution?.status === "running" ? (id ?? null) : null
  )

  // Parse workflow nodes from YAML content
  const workflowContent = workflow?.content
  const workflowNodes = useMemo(() => {
    if (!workflowContent) return []
    return extractNodesFromYaml(workflowContent)
  }, [workflowContent])

  // Merge execution node results with live results
  const nodeResults = useMemo(() => {
    const results: Record<string, NodeResult> = {}

    // Add results from execution detail
    execution?.node_executions?.forEach((nodeExec) => {
      results[nodeExec.node_id] = {
        node_id: nodeExec.node_id,
        status: nodeExec.status,
        started_at: nodeExec.started_at ?? undefined,
        completed_at: nodeExec.finished_at ?? undefined,
        duration_ms: nodeExec.duration_ms ?? undefined,
        error: nodeExec.error ?? undefined,
      }
    })

    // Override with live results
    Object.entries(liveResults).forEach(([nodeId, nodeExec]) => {
      results[nodeId] = {
        node_id: nodeExec.node_id,
        status: nodeExec.status,
        started_at: nodeExec.started_at ?? undefined,
        completed_at: nodeExec.finished_at ?? undefined,
        duration_ms: nodeExec.duration_ms ?? undefined,
        error: nodeExec.error ?? undefined,
      }
    })

    return results
  }, [execution?.node_executions, liveResults])

  const isLoading = execLoading || workflowLoading

  if (isLoading) {
    return (
      <div className="flex h-[calc(100vh-8rem)] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  if (execError || !execution) {
    return (
      <div className="space-y-4">
        <Link
          to="/executions"
          className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Executions
        </Link>
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>
            {execError
              ? "Failed to load execution. Please try again."
              : "Execution not found."}
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
            to="/executions"
            className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              Execution: {execution.workflow_name}
            </h1>
            <p className="text-sm text-muted-foreground">
              {execution.id.slice(0, 8)}...
              {isConnected && execution.status === "running" && (
                <span className="ml-2 text-green-500">Live</span>
              )}
            </p>
          </div>
        </div>
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="flow" className="gap-2">
              <GitBranch className="h-4 w-4" />
              Flow
            </TabsTrigger>
            <TabsTrigger value="logs" className="gap-2">
              <ScrollText className="h-4 w-4" />
              Logs
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden mt-4">
        {activeTab === "flow" ? (
          <>
            {/* Flow Canvas */}
            <div className="flex-1 border rounded-lg overflow-hidden">
              {workflowNodes.length > 0 ? (
                <FlowCanvas
                  workflowNodes={workflowNodes}
                  nodeResults={nodeResults}
                  onNodeClick={setSelectedNodeId}
                />
              ) : (
                <div className="flex h-full items-center justify-center text-muted-foreground">
                  {workflow
                    ? "No nodes found in workflow"
                    : "Workflow data not available"}
                </div>
              )}
            </div>

            {/* Sidebar */}
            <div className="w-80 border-l ml-4 overflow-hidden">
              <ExecutionSidebar
                executionId={execution.id}
                workflowName={execution.workflow_name}
                status={execution.status}
                startedAt={execution.started_at}
                completedAt={execution.finished_at ?? undefined}
                nodeResults={nodeResults}
                selectedNodeId={selectedNodeId}
                onNodeSelect={setSelectedNodeId}
              />
            </div>
          </>
        ) : (
          /* Logs View */
          <div className="flex-1 relative">
            <LiveLogViewer
              executionId={execution.id}
              isRunning={execution.status === "running"}
            />
          </div>
        )}
      </div>
    </div>
  )
}

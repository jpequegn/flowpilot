import { useMemo, useCallback, useState } from "react"
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type NodeTypes,
} from "@xyflow/react"
import "@xyflow/react/dist/style.css"

import {
  ShellNode,
  HttpNode,
  FileNode,
  ConditionNode,
  LoopNode,
  DelayNode,
  ParallelNode,
  ClaudeNode,
  LogNode,
  DefaultNode,
} from "./nodes"
import {
  parseWorkflowToFlow,
  type NodeResult,
  type FlowNode,
} from "@/lib/flowParser"
import type { WorkflowNode } from "@/types"

// Register custom node types
const nodeTypes: NodeTypes = {
  shell: ShellNode,
  http: HttpNode,
  file: FileNode,
  condition: ConditionNode,
  loop: LoopNode,
  delay: DelayNode,
  parallel: ParallelNode,
  claude: ClaudeNode,
  log: LogNode,
  default: DefaultNode,
}

interface FlowCanvasProps {
  workflowNodes: WorkflowNode[]
  nodeResults?: Record<string, NodeResult>
  onNodeClick?: (nodeId: string) => void
}

export function FlowCanvas({
  workflowNodes,
  nodeResults,
  onNodeClick,
}: FlowCanvasProps) {
  const [, setSelectedNodeId] = useState<string | null>(null)

  // Parse workflow to React Flow format
  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => parseWorkflowToFlow(workflowNodes, nodeResults),
    [workflowNodes, nodeResults]
  )

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)

  // Update nodes when nodeResults change
  useMemo(() => {
    const { nodes: newNodes, edges: newEdges } = parseWorkflowToFlow(
      workflowNodes,
      nodeResults
    )
    setNodes(newNodes)
    setEdges(newEdges)
  }, [workflowNodes, nodeResults, setNodes, setEdges])

  // Handle node click
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: FlowNode) => {
      setSelectedNodeId(node.id)
      onNodeClick?.(node.id)
    },
    [onNodeClick]
  )

  // MiniMap node color based on status
  const getNodeColor = useCallback((node: FlowNode) => {
    const status = node.data?.status
    switch (status) {
      case "running":
        return "#3b82f6"
      case "completed":
        return "#22c55e"
      case "failed":
        return "#ef4444"
      case "cancelled":
        return "#eab308"
      default:
        return "#94a3b8"
    }
  }, [])

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
        minZoom={0.1}
        maxZoom={2}
        defaultEdgeOptions={{
          type: "smoothstep",
        }}
      >
        <Background gap={16} size={1} color="#e2e8f0" />
        <Controls />
        <MiniMap
          nodeColor={getNodeColor}
          maskColor="rgba(0, 0, 0, 0.1)"
          className="bg-white rounded-lg shadow-md"
        />
      </ReactFlow>
    </div>
  )
}

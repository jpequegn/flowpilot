import dagre from "dagre"
import type { Node, Edge } from "@xyflow/react"
import type { WorkflowNode, ExecutionStatusType } from "@/types"

// Node result from execution
export interface NodeResult {
  node_id: string
  status: ExecutionStatusType
  started_at?: string
  completed_at?: string
  duration_ms?: number
  outputs?: Record<string, unknown>
  error?: string
}

// Flow node data structure
export interface FlowNodeData extends Record<string, unknown> {
  label: string
  nodeType: string
  status?: ExecutionStatusType
  duration_ms?: number
  error?: string
  config: Record<string, unknown>
}

// Custom flow node type for React Flow v12
export type FlowNode = Node<FlowNodeData>

// Map backend node types to flow node types
export function getNodeFlowType(backendType: string): string {
  const typeMap: Record<string, string> = {
    shell: "shell",
    http: "http",
    file_read: "file",
    file_write: "file",
    condition: "condition",
    loop: "loop",
    delay: "delay",
    parallel: "parallel",
    claude_cli: "claude",
    claude_api: "claude",
    log: "log",
  }
  return typeMap[backendType] || "default"
}

// Parse workflow nodes to React Flow format
export function parseWorkflowToFlow(
  nodes: WorkflowNode[],
  nodeResults?: Record<string, NodeResult>
): { nodes: Node<FlowNodeData>[]; edges: Edge[] } {
  // Create nodes
  const flowNodes: Node<FlowNodeData>[] = nodes.map((node) => ({
    id: node.id,
    type: getNodeFlowType(node.type),
    position: { x: 0, y: 0 }, // Will be calculated by dagre
    data: {
      label: node.id,
      nodeType: node.type,
      status: nodeResults?.[node.id]?.status,
      duration_ms: nodeResults?.[node.id]?.duration_ms,
      error: nodeResults?.[node.id]?.error,
      config: node.config,
    },
  }))

  // Create edges from dependencies
  const flowEdges: Edge[] = []
  nodes.forEach((node) => {
    node.depends_on?.forEach((dep) => {
      const isRunning = nodeResults?.[dep]?.status === "running"
      const isCompleted = nodeResults?.[dep]?.status === "completed"

      flowEdges.push({
        id: `${dep}-${node.id}`,
        source: dep,
        target: node.id,
        animated: isRunning,
        style: {
          stroke: isCompleted ? "#22c55e" : isRunning ? "#3b82f6" : "#94a3b8",
          strokeWidth: 2,
        },
      })
    })
  })

  // Apply dagre layout
  return applyDagreLayout(flowNodes, flowEdges)
}

// Apply dagre automatic layout
function applyDagreLayout(
  nodes: Node<FlowNodeData>[],
  edges: Edge[]
): { nodes: Node<FlowNodeData>[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: "TB", nodesep: 60, ranksep: 100 })
  g.setDefaultEdgeLabel(() => ({}))

  // Set node dimensions
  const nodeWidth = 220
  const nodeHeight = 80

  nodes.forEach((node) => {
    g.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })

  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target)
  })

  dagre.layout(g)

  // Update node positions
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

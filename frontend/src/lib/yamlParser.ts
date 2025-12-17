import { parse } from "yaml"
import type { WorkflowNode } from "@/types"

interface ParsedWorkflow {
  name: string
  description?: string
  version: number | string
  nodes: WorkflowNode[]
  triggers?: unknown[]
  inputs?: Record<string, unknown>
}

export function parseWorkflowYaml(content: string): ParsedWorkflow | null {
  try {
    const parsed = parse(content) as ParsedWorkflow
    return parsed
  } catch (e) {
    console.error("Failed to parse workflow YAML:", e)
    return null
  }
}

export function extractNodesFromYaml(content: string): WorkflowNode[] {
  const parsed = parseWorkflowYaml(content)
  if (!parsed?.nodes) return []

  return parsed.nodes.map((node) => ({
    id: node.id,
    type: node.type,
    config: node.config || {},
    depends_on: node.depends_on,
  }))
}

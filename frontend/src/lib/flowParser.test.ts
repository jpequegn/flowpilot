import { describe, it, expect } from "vitest"
import {
  parseWorkflowToFlow,
  getNodeFlowType,
  type NodeResult,
} from "./flowParser"
import type { WorkflowNode } from "@/types"

describe("flowParser", () => {
  describe("getNodeFlowType", () => {
    it("maps shell type correctly", () => {
      expect(getNodeFlowType("shell")).toBe("shell")
    })

    it("maps http type correctly", () => {
      expect(getNodeFlowType("http")).toBe("http")
    })

    it("maps file_read to file type", () => {
      expect(getNodeFlowType("file_read")).toBe("file")
    })

    it("maps file_write to file type", () => {
      expect(getNodeFlowType("file_write")).toBe("file")
    })

    it("maps condition type correctly", () => {
      expect(getNodeFlowType("condition")).toBe("condition")
    })

    it("maps loop type correctly", () => {
      expect(getNodeFlowType("loop")).toBe("loop")
    })

    it("maps delay type correctly", () => {
      expect(getNodeFlowType("delay")).toBe("delay")
    })

    it("maps parallel type correctly", () => {
      expect(getNodeFlowType("parallel")).toBe("parallel")
    })

    it("maps claude_cli to claude type", () => {
      expect(getNodeFlowType("claude_cli")).toBe("claude")
    })

    it("maps claude_api to claude type", () => {
      expect(getNodeFlowType("claude_api")).toBe("claude")
    })

    it("maps log type correctly", () => {
      expect(getNodeFlowType("log")).toBe("log")
    })

    it("returns default for unknown types", () => {
      expect(getNodeFlowType("unknown")).toBe("default")
    })
  })

  describe("parseWorkflowToFlow", () => {
    it("converts workflow nodes to flow nodes with positions", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: { command: "echo hello" } },
        {
          id: "node2",
          type: "http",
          config: { url: "https://example.com" },
          depends_on: ["node1"],
        },
      ]

      const result = parseWorkflowToFlow(workflowNodes)

      expect(result.nodes).toHaveLength(2)
      expect(result.nodes[0].id).toBe("node1")
      expect(result.nodes[0].type).toBe("shell")
      expect(result.nodes[0].data.label).toBe("node1")
      expect(result.nodes[0].data.nodeType).toBe("shell")
      expect(result.nodes[0].data.config).toEqual({ command: "echo hello" })
      expect(result.nodes[0].position).toBeDefined()
      expect(result.nodes[0].position.x).toBeTypeOf("number")
      expect(result.nodes[0].position.y).toBeTypeOf("number")

      expect(result.nodes[1].id).toBe("node2")
      expect(result.nodes[1].type).toBe("http")
    })

    it("creates edges from dependencies", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: {} },
        { id: "node2", type: "shell", config: {}, depends_on: ["node1"] },
        {
          id: "node3",
          type: "shell",
          config: {},
          depends_on: ["node1", "node2"],
        },
      ]

      const { edges } = parseWorkflowToFlow(workflowNodes)

      expect(edges).toHaveLength(3)
      expect(edges[0]).toMatchObject({
        id: "node1-node2",
        source: "node1",
        target: "node2",
      })
      expect(edges[1]).toMatchObject({
        id: "node1-node3",
        source: "node1",
        target: "node3",
      })
      expect(edges[2]).toMatchObject({
        id: "node2-node3",
        source: "node2",
        target: "node3",
      })
    })

    it("applies node results status to flow nodes", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: {} },
        { id: "node2", type: "shell", config: {}, depends_on: ["node1"] },
      ]

      const nodeResults: Record<string, NodeResult> = {
        node1: {
          node_id: "node1",
          status: "completed",
          duration_ms: 100,
        },
        node2: {
          node_id: "node2",
          status: "running",
        },
      }

      const { nodes, edges } = parseWorkflowToFlow(workflowNodes, nodeResults)

      expect(nodes[0].data.status).toBe("completed")
      expect(nodes[0].data.duration_ms).toBe(100)
      expect(nodes[1].data.status).toBe("running")

      // Edge from completed node should be green
      expect(edges[0].style?.stroke).toBe("#22c55e")
    })

    it("animates edges when source node is running", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: {} },
        { id: "node2", type: "shell", config: {}, depends_on: ["node1"] },
      ]

      const nodeResults: Record<string, NodeResult> = {
        node1: {
          node_id: "node1",
          status: "running",
        },
      }

      const { edges } = parseWorkflowToFlow(workflowNodes, nodeResults)

      expect(edges[0].animated).toBe(true)
      expect(edges[0].style?.stroke).toBe("#3b82f6") // Blue for running
    })

    it("applies layout with dagre algorithm", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: {} },
        { id: "node2", type: "shell", config: {}, depends_on: ["node1"] },
        { id: "node3", type: "shell", config: {}, depends_on: ["node2"] },
      ]

      const { nodes } = parseWorkflowToFlow(workflowNodes)

      // Nodes should have increasing y positions (top to bottom layout)
      expect(nodes[0].position.y).toBeLessThan(nodes[1].position.y)
      expect(nodes[1].position.y).toBeLessThan(nodes[2].position.y)
    })

    it("handles parallel branches in layout", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "start", type: "shell", config: {} },
        { id: "branch1", type: "shell", config: {}, depends_on: ["start"] },
        { id: "branch2", type: "shell", config: {}, depends_on: ["start"] },
        {
          id: "end",
          type: "shell",
          config: {},
          depends_on: ["branch1", "branch2"],
        },
      ]

      const { nodes } = parseWorkflowToFlow(workflowNodes)

      const branch1 = nodes.find((n) => n.id === "branch1")!
      const branch2 = nodes.find((n) => n.id === "branch2")!

      // Parallel branches should be at same y level
      expect(branch1.position.y).toBe(branch2.position.y)
      // But different x positions
      expect(branch1.position.x).not.toBe(branch2.position.x)
    })

    it("handles empty nodes array", () => {
      const { nodes, edges } = parseWorkflowToFlow([])

      expect(nodes).toHaveLength(0)
      expect(edges).toHaveLength(0)
    })

    it("handles nodes without dependencies", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: {} },
        { id: "node2", type: "http", config: {} },
      ]

      const { nodes, edges } = parseWorkflowToFlow(workflowNodes)

      expect(nodes).toHaveLength(2)
      expect(edges).toHaveLength(0)
    })

    it("includes error in node data when present", () => {
      const workflowNodes: WorkflowNode[] = [
        { id: "node1", type: "shell", config: {} },
      ]

      const nodeResults: Record<string, NodeResult> = {
        node1: {
          node_id: "node1",
          status: "failed",
          error: "Command failed with exit code 1",
        },
      }

      const { nodes } = parseWorkflowToFlow(workflowNodes, nodeResults)

      expect(nodes[0].data.status).toBe("failed")
      expect(nodes[0].data.error).toBe("Command failed with exit code 1")
    })
  })
})

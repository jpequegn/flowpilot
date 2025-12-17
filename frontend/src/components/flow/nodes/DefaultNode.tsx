import { Box } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function DefaultNode({ data, selected }: NodeProps<FlowNode>) {
  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<Box className="w-4 h-4" />}
      iconColor="text-gray-500"
    >
      <div className="mt-2 text-xs text-muted-foreground">{data.nodeType}</div>
    </BaseNode>
  )
}

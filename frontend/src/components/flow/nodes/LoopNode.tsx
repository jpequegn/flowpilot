import { Repeat } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function LoopNode({ data, selected }: NodeProps<FlowNode>) {
  const items = data.config?.items as string | undefined
  const maxIterations = data.config?.max_iterations as number | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<Repeat className="w-4 h-4" />}
      iconColor="text-indigo-500"
    >
      <div className="mt-2 text-xs text-muted-foreground">
        {items && <div className="truncate">items: {items}</div>}
        {maxIterations && <div>max: {maxIterations}</div>}
      </div>
    </BaseNode>
  )
}

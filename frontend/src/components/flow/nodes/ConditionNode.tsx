import { GitBranch } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function ConditionNode({ data, selected }: NodeProps<FlowNode>) {
  const condition = data.config?.condition as string | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<GitBranch className="w-4 h-4" />}
      iconColor="text-amber-500"
    >
      {condition && (
        <div className="mt-2 text-xs text-muted-foreground font-mono truncate">
          if: {condition}
        </div>
      )}
    </BaseNode>
  )
}

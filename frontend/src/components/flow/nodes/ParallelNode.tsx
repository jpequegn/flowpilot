import { GitFork } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function ParallelNode({ data, selected }: NodeProps<FlowNode>) {
  const branches = data.config?.branches as unknown[] | undefined
  const maxConcurrency = data.config?.max_concurrency as number | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<GitFork className="w-4 h-4" />}
      iconColor="text-teal-500"
    >
      <div className="mt-2 text-xs text-muted-foreground">
        {branches && <div>{branches.length} branches</div>}
        {maxConcurrency && <div>max: {maxConcurrency}</div>}
      </div>
    </BaseNode>
  )
}

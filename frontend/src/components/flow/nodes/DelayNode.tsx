import { Clock } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function DelayNode({ data, selected }: NodeProps<FlowNode>) {
  const seconds = data.config?.seconds as number | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<Clock className="w-4 h-4" />}
      iconColor="text-slate-500"
    >
      {seconds !== undefined && (
        <div className="mt-2 text-xs text-muted-foreground">{seconds}s</div>
      )}
    </BaseNode>
  )
}

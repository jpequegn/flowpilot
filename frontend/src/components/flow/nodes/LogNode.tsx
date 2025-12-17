import { MessageSquare } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function LogNode({ data, selected }: NodeProps<FlowNode>) {
  const message = data.config?.message as string | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<MessageSquare className="w-4 h-4" />}
      iconColor="text-emerald-500"
    >
      {message && (
        <div className="mt-2 text-xs text-muted-foreground truncate">
          {message}
        </div>
      )}
    </BaseNode>
  )
}

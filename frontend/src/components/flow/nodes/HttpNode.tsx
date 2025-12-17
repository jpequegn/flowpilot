import { Globe } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function HttpNode({ data, selected }: NodeProps<FlowNode>) {
  const method = (data.config?.method as string | undefined)?.toUpperCase()
  const url = data.config?.url as string | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<Globe className="w-4 h-4" />}
      iconColor="text-blue-500"
    >
      {(method || url) && (
        <div className="mt-2 text-xs text-muted-foreground truncate">
          {method && (
            <span className="font-semibold text-blue-600">{method}</span>
          )}{" "}
          {url}
        </div>
      )}
    </BaseNode>
  )
}

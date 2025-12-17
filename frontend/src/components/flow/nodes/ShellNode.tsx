import { Terminal } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function ShellNode({ data, selected }: NodeProps<FlowNode>) {
  const command = data.config?.command as string | undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<Terminal className="w-4 h-4" />}
      iconColor="text-purple-500"
    >
      {command && (
        <div className="mt-2 text-xs text-muted-foreground font-mono truncate">
          $ {command}
        </div>
      )}
    </BaseNode>
  )
}

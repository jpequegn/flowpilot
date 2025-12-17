import { FileText } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function FileNode({ data, selected }: NodeProps<FlowNode>) {
  const path = data.config?.path as string | undefined
  const isWrite =
    data.nodeType === "file_write" || data.config?.content !== undefined

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<FileText className="w-4 h-4" />}
      iconColor={isWrite ? "text-orange-500" : "text-cyan-500"}
    >
      {path && (
        <div className="mt-2 text-xs text-muted-foreground truncate">
          <span className="font-semibold">{isWrite ? "Write:" : "Read:"}</span>{" "}
          {path}
        </div>
      )}
    </BaseNode>
  )
}

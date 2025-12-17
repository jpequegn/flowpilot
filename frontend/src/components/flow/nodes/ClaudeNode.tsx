import { Sparkles } from "lucide-react"
import type { NodeProps } from "@xyflow/react"
import { BaseNode } from "../BaseNode"
import type { FlowNode } from "@/lib/flowParser"

export function ClaudeNode({ data, selected }: NodeProps<FlowNode>) {
  const prompt = data.config?.prompt as string | undefined
  const model = data.config?.model as string | undefined
  const isCli = data.nodeType === "claude_cli"

  return (
    <BaseNode
      label={data.label}
      status={data.status}
      duration_ms={data.duration_ms}
      error={data.error}
      selected={selected}
      icon={<Sparkles className="w-4 h-4" />}
      iconColor="text-violet-500"
    >
      <div className="mt-2 text-xs text-muted-foreground">
        <span className="font-semibold">{isCli ? "CLI" : "API"}</span>
        {model && <span className="ml-1">({model})</span>}
      </div>
      {prompt && (
        <div className="mt-1 text-xs text-muted-foreground truncate">
          {prompt.slice(0, 50)}...
        </div>
      )}
    </BaseNode>
  )
}

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { X } from "lucide-react"
import type { ExecutionStatusType } from "@/types"

export interface ExecutionFiltersValue {
  workflow?: string
  status?: ExecutionStatusType | "all"
}

interface ExecutionFiltersProps {
  value: ExecutionFiltersValue
  onChange: (value: ExecutionFiltersValue) => void
  workflows?: string[]
}

export function ExecutionFilters({
  value,
  onChange,
  workflows = [],
}: ExecutionFiltersProps) {
  const hasFilters = value.workflow || (value.status && value.status !== "all")

  const handleClear = () => {
    onChange({ workflow: undefined, status: undefined })
  }

  return (
    <div className="flex items-center gap-4">
      <div className="flex-1 max-w-sm">
        <Input
          placeholder="Filter by workflow name..."
          value={value.workflow ?? ""}
          onChange={(e) =>
            onChange({ ...value, workflow: e.target.value || undefined })
          }
        />
      </div>

      <Select
        value={value.status ?? "all"}
        onValueChange={(status) =>
          onChange({
            ...value,
            status:
              status === "all" ? undefined : (status as ExecutionStatusType),
          })
        }
      >
        <SelectTrigger className="w-[150px]">
          <SelectValue placeholder="Status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="all">All statuses</SelectItem>
          <SelectItem value="running">Running</SelectItem>
          <SelectItem value="completed">Completed</SelectItem>
          <SelectItem value="failed">Failed</SelectItem>
          <SelectItem value="pending">Pending</SelectItem>
          <SelectItem value="cancelled">Cancelled</SelectItem>
        </SelectContent>
      </Select>

      {workflows.length > 0 && (
        <Select
          value={value.workflow ?? "all"}
          onValueChange={(workflow) =>
            onChange({
              ...value,
              workflow: workflow === "all" ? undefined : workflow,
            })
          }
        >
          <SelectTrigger className="w-[200px]">
            <SelectValue placeholder="Workflow" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All workflows</SelectItem>
            {workflows.map((w) => (
              <SelectItem key={w} value={w}>
                {w}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}

      {hasFilters && (
        <Button variant="ghost" size="sm" onClick={handleClear}>
          <X className="h-4 w-4 mr-1" />
          Clear
        </Button>
      )}
    </div>
  )
}

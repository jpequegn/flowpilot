import { Link } from "react-router-dom"
import { MoreHorizontal, Play, Pencil, Trash2 } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { WorkflowListItem } from "@/types"

interface WorkflowCardProps {
  workflow: WorkflowListItem
  onRun?: (name: string) => void
  onDelete?: (name: string) => void
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Unknown"

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffDays > 0) {
    return diffDays === 1 ? "1 day ago" : `${diffDays} days ago`
  }
  if (diffHours > 0) {
    return diffHours === 1 ? "1 hour ago" : `${diffHours} hours ago`
  }
  if (diffMins > 0) {
    return diffMins === 1 ? "1 minute ago" : `${diffMins} minutes ago`
  }
  return "Just now"
}

export function WorkflowCard({ workflow, onRun, onDelete }: WorkflowCardProps) {
  return (
    <Card className="group hover:border-primary/50 transition-colors">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="space-y-1">
            <Link
              to={`/workflows/${encodeURIComponent(workflow.name)}`}
              className="hover:underline"
            >
              <CardTitle className="text-lg">{workflow.name}</CardTitle>
            </Link>
            <CardDescription>
              {workflow.description || "No description"}
            </CardDescription>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">Open menu</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onRun?.(workflow.name)}>
                <Play className="mr-2 h-4 w-4" />
                Run Workflow
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link to={`/workflows/${encodeURIComponent(workflow.name)}`}>
                  <Pencil className="mr-2 h-4 w-4" />
                  Edit
                </Link>
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                className="text-destructive focus:text-destructive"
                onClick={() => onDelete?.(workflow.name)}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <Badge variant="outline">v{workflow.version}</Badge>
          <span>Updated {formatRelativeTime(workflow.updated_at)}</span>
        </div>
      </CardContent>
    </Card>
  )
}

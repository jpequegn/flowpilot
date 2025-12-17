import { useRef, useState, useEffect, useMemo } from "react"
import { useVirtualizer } from "@tanstack/react-virtual"
import { format } from "date-fns"
import { ArrowDown, Download, Search, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { cn } from "@/lib/utils"
import { useLiveLogs } from "@/hooks/useExecutions"
import type { LogEntry } from "@/types"

interface LiveLogViewerProps {
  executionId: string
  isRunning?: boolean
}

const levelConfig = {
  info: { color: "text-blue-400", label: "INFO" },
  warn: { color: "text-yellow-400", label: "WARN" },
  error: { color: "text-red-400", label: "ERROR" },
  debug: { color: "text-gray-400", label: "DEBUG" },
}

function LogLine({ log }: { log: LogEntry }) {
  const config = levelConfig[log.level]

  return (
    <div className="flex gap-4 px-4 py-1 hover:bg-slate-800/50 font-mono text-xs">
      <span className="text-slate-500 w-24 flex-shrink-0">
        {format(new Date(log.timestamp), "HH:mm:ss.SSS")}
      </span>
      <span className={cn("w-12 flex-shrink-0", config.color)}>
        [{config.label}]
      </span>
      {log.node_id && (
        <span className="text-purple-400 w-24 flex-shrink-0 truncate">
          {log.node_id}
        </span>
      )}
      <span className="flex-1 whitespace-pre-wrap break-all text-slate-100">
        {log.message}
      </span>
    </div>
  )
}

export function LiveLogViewer({ executionId, isRunning }: LiveLogViewerProps) {
  const parentRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [levelFilter, setLevelFilter] = useState<Set<string>>(
    new Set(["info", "warn", "error", "debug"])
  )
  const [searchQuery, setSearchQuery] = useState("")

  const { logs, isConnected } = useLiveLogs(isRunning ? executionId : null)

  // Filter logs by level and search query
  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      if (!levelFilter.has(log.level)) return false
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        return (
          log.message.toLowerCase().includes(query) ||
          log.node_id?.toLowerCase().includes(query)
        )
      }
      return true
    })
  }, [logs, levelFilter, searchQuery])

  const virtualizer = useVirtualizer({
    count: filteredLogs.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 24,
    overscan: 10,
  })

  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (autoScroll && filteredLogs.length > 0) {
      virtualizer.scrollToIndex(filteredLogs.length - 1)
    }
  }, [filteredLogs.length, autoScroll, virtualizer])

  // Detect user scroll to pause auto-scroll
  const handleScroll = () => {
    const parent = parentRef.current
    if (!parent) return
    const atBottom =
      Math.abs(parent.scrollHeight - parent.scrollTop - parent.clientHeight) <
      10
    setAutoScroll(atBottom)
  }

  const toggleLevel = (level: string) => {
    const newFilter = new Set(levelFilter)
    if (newFilter.has(level)) {
      newFilter.delete(level)
    } else {
      newFilter.add(level)
    }
    setLevelFilter(newFilter)
  }

  const exportLogs = () => {
    const content = filteredLogs
      .map(
        (log) =>
          `${log.timestamp} [${log.level.toUpperCase()}] ${log.node_id ? `[${log.node_id}] ` : ""}${log.message}`
      )
      .join("\n")
    const blob = new Blob([content], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = `execution-${executionId}-logs.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full border rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-2 border-b bg-muted/30">
        <div className="flex items-center gap-2">
          {(["info", "warn", "error", "debug"] as const).map((level) => (
            <Button
              key={level}
              size="sm"
              variant={levelFilter.has(level) ? "default" : "outline"}
              onClick={() => toggleLevel(level)}
              className={cn(
                "h-7 px-2 text-xs",
                levelFilter.has(level) && levelConfig[level].color
              )}
            >
              {level}
            </Button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-8 w-48 pl-8 text-sm"
            />
            {searchQuery && (
              <Button
                variant="ghost"
                size="sm"
                className="absolute right-1 top-1/2 -translate-y-1/2 h-6 w-6 p-0"
                onClick={() => setSearchQuery("")}
              >
                <X className="h-3 w-3" />
              </Button>
            )}
          </div>
          <Button size="sm" variant="outline" onClick={exportLogs}>
            <Download className="h-4 w-4 mr-1" />
            Export
          </Button>
        </div>
      </div>

      {/* Connection status */}
      {isRunning && (
        <div
          className={cn(
            "px-2 py-1 text-xs",
            isConnected
              ? "bg-green-500/10 text-green-500"
              : "bg-yellow-500/10 text-yellow-500"
          )}
        >
          {isConnected ? "Connected - Live streaming" : "Connecting..."}
        </div>
      )}

      {/* Log content */}
      <div
        ref={parentRef}
        className="flex-1 overflow-auto bg-slate-950"
        onScroll={handleScroll}
      >
        {filteredLogs.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            {logs.length === 0 ? "No logs yet" : "No matching logs"}
          </div>
        ) : (
          <div
            style={{
              height: `${virtualizer.getTotalSize()}px`,
              width: "100%",
              position: "relative",
            }}
          >
            {virtualizer.getVirtualItems().map((virtualItem) => {
              const log = filteredLogs[virtualItem.index]
              return (
                <div
                  key={virtualItem.key}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    width: "100%",
                    height: `${virtualItem.size}px`,
                    transform: `translateY(${virtualItem.start}px)`,
                  }}
                >
                  <LogLine log={log} />
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Resume auto-scroll button */}
      {!autoScroll && filteredLogs.length > 0 && (
        <div className="absolute bottom-4 right-4">
          <Button
            onClick={() => {
              setAutoScroll(true)
              virtualizer.scrollToIndex(filteredLogs.length - 1)
            }}
          >
            <ArrowDown className="w-4 h-4 mr-2" />
            Resume
          </Button>
        </div>
      )}
    </div>
  )
}

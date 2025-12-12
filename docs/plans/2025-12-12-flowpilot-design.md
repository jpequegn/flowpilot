# FlowPilot Design Document

**Date:** 2025-12-12
**Status:** Approved
**Version:** 1.0

## Overview

FlowPilot is a workflow automation tool for macOS that enables power users to schedule and execute sets of tasks, with native Claude Code integration. It follows an n8n-inspired architecture but with a YAML-first approach optimized for technical users.

## Goals

- **Power user focused**: Good UI, extensible, shareable workflows
- **YAML-first**: Workflows defined as code, version-control friendly
- **Claude Code native**: First-class integration with Claude CLI and API
- **macOS optimized**: Leverages launchd, FSEvents, native notifications

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (localhost:8080)                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  React Frontend                                              ││
│  │  • Workflow list & editor (Monaco/CodeMirror for YAML)      ││
│  │  • Visual flow preview (React Flow)                         ││
│  │  • Execution logs & history                                 ││
│  │  • Schedule management                                       ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │ REST API
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Python Backend (FastAPI)                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐ │
│  │ API Routes   │ │ Scheduler    │ │ Workflow Engine          │ │
│  │ • CRUD       │ │ • APScheduler│ │ • YAML parser            │ │
│  │ • Execute    │ │ • Cron jobs  │ │ • Node executor          │ │
│  │ • Logs       │ │ • File watch │ │ • Claude CLI/API runner  │ │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────────┐
│ ~/.flowpilot │    │ SQLite DB    │    │ External         │
│ /workflows/  │    │ • Executions │    │ • Claude CLI     │
│   *.yaml     │    │ • Schedules  │    │ • Claude API     │
│              │    │ • Logs       │    │ • Shell commands │
└──────────────┘    └──────────────┘    └──────────────────┘
```

## Workflow Format

```yaml
name: daily-code-review
description: Review uncommitted changes every morning
version: 1

triggers:
  - type: cron
    schedule: "0 9 * * 1-5"  # 9am weekdays
  - type: manual

inputs:
  repo_path:
    type: string
    default: "~/Code/myproject"

nodes:
  - id: get-diff
    type: shell
    command: "cd {{ inputs.repo_path }} && git diff"

  - id: review-code
    type: claude-cli
    prompt: |
      Review this git diff for issues:
      {{ nodes.get-diff.stdout }}
    options:
      model: sonnet

  - id: check-issues
    type: condition
    if: "'critical' in nodes.review-code.output"
    then: notify-urgent
    else: save-report

  - id: notify-urgent
    type: shell
    command: |
      osascript -e 'display notification "{{ nodes.review-code.output | truncate(100) }}" with title "Critical Issue Found"'

  - id: save-report
    type: file-write
    path: "~/reports/{{ date('YYYY-MM-DD') }}-review.md"
    content: "{{ nodes.review-code.output }}"

settings:
  timeout: 300
  retry: 2
  on_error: continue
```

## Node Types (v1)

### Triggers

| Type | Config | Description |
|------|--------|-------------|
| `cron` | `schedule: "0 * * * *"` | Standard cron expression |
| `interval` | `every: 30m` | Simple intervals (5s, 10m, 2h) |
| `file-watch` | `path, events` | FSEvents watcher |
| `webhook` | `path: /hooks/...` | HTTP POST endpoint |
| `manual` | - | UI/CLI triggered |

### Actions

| Type | Config | Description |
|------|--------|-------------|
| `shell` | `command` | Run shell command |
| `http` | `url, method, headers, body` | HTTP requests |
| `file-read` | `path` | Read file content |
| `file-write` | `path, content` | Write to file |
| `claude-cli` | `prompt, options` | Claude Code CLI |
| `claude-api` | `prompt, model, system` | Direct Anthropic API |

### Logic

| Type | Config | Description |
|------|--------|-------------|
| `condition` | `if, then, else` | Branching |
| `loop` | `for, node` | Iteration |
| `delay` | `duration` | Wait |
| `parallel` | `nodes` | Concurrent execution |

### Node Output Schema

```python
{
  "status": "success" | "error" | "skipped",
  "stdout": "...",
  "stderr": "...",
  "output": "...",
  "data": {...},
  "duration_ms": 1234,
  "error": "..."
}
```

## CLI Interface

```bash
# Setup
flowpilot init

# Daemon
flowpilot serve [--daemon]
flowpilot stop

# Workflows
flowpilot list
flowpilot new <name>
flowpilot validate <name>
flowpilot run <name> [--input key=value]

# Scheduling
flowpilot enable <name>
flowpilot disable <name>
flowpilot status

# Logs
flowpilot logs <name>
flowpilot history <name>

# Sharing
flowpilot export <name>
flowpilot import <file>
```

## Directory Structure

```
~/.flowpilot/
├── config.yaml
├── workflows/
│   └── *.yaml
├── flowpilot.db
└── logs/
```

## Tech Stack

### Backend (Python)

- **FastAPI**: Web framework
- **APScheduler**: Task scheduling
- **watchdog**: File system events
- **PyYAML + Pydantic**: YAML parsing + validation
- **Jinja2**: Templating
- **SQLAlchemy + SQLite**: Database
- **anthropic**: Claude API SDK
- **Typer**: CLI framework

### Frontend (React)

- **React + Vite**: Framework + bundler
- **shadcn/ui**: UI components
- **Monaco Editor**: YAML editing
- **React Flow**: Flow visualization
- **Zustand**: State management
- **TanStack Query**: API state

### Distribution

- PyPI package (`pip install flowpilot`)
- Frontend embedded in package
- launchd plist for daemon mode

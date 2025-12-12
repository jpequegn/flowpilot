# FlowPilot Implementation Plan

## Phase 1: Foundation (MVP)

### 1.1 Project Setup
- [ ] Python package structure with pyproject.toml
- [ ] Development environment (uv, ruff, mypy)
- [ ] Basic CI/CD (GitHub Actions)

### 1.2 Core Engine
- [ ] Workflow YAML schema (Pydantic models)
- [ ] YAML parser with validation
- [ ] Node execution framework (base classes)
- [ ] Execution context (variable passing between nodes)
- [ ] Jinja2 templating integration

### 1.3 Basic Node Types
- [ ] Shell node (subprocess execution)
- [ ] File read/write nodes
- [ ] HTTP request node
- [ ] Condition node (if/then/else)

### 1.4 CLI Foundation
- [ ] `flowpilot init` - create ~/.flowpilot structure
- [ ] `flowpilot validate` - check workflow syntax
- [ ] `flowpilot run` - execute workflow
- [ ] `flowpilot list` - list workflows

### 1.5 Storage Layer
- [ ] SQLite schema (executions, logs)
- [ ] SQLAlchemy models
- [ ] Execution logging

---

## Phase 2: Scheduling & Triggers

### 2.1 Scheduler
- [ ] APScheduler integration
- [ ] Cron trigger support
- [ ] Interval trigger support
- [ ] Job persistence (SQLite job store)

### 2.2 File Watching
- [ ] watchdog integration
- [ ] File watch trigger type
- [ ] Event filtering (created, modified, deleted)

### 2.3 Webhook Triggers
- [ ] FastAPI webhook endpoints
- [ ] Webhook trigger type
- [ ] Request body access in workflow

### 2.4 CLI Extensions
- [ ] `flowpilot enable/disable` - manage schedules
- [ ] `flowpilot status` - show active schedules
- [ ] `flowpilot logs` - view execution logs

---

## Phase 3: Claude Integration

### 3.1 Claude CLI Node
- [ ] Subprocess wrapper for `claude` command
- [ ] Prompt templating
- [ ] Output capture and parsing
- [ ] Options passthrough (model, etc.)

### 3.2 Claude API Node
- [ ] anthropic SDK integration
- [ ] API key configuration
- [ ] Model selection
- [ ] System prompt support
- [ ] Streaming output (optional)

### 3.3 Error Handling
- [ ] Timeout handling
- [ ] Retry logic
- [ ] Error context preservation

---

## Phase 4: Advanced Logic

### 4.1 Loop Node
- [ ] For-each iteration
- [ ] Loop variable access
- [ ] Break conditions

### 4.2 Parallel Node
- [ ] Concurrent execution
- [ ] Result aggregation
- [ ] Failure handling (fail-fast vs continue)

### 4.3 Delay Node
- [ ] Duration parsing (5s, 10m, 1h)
- [ ] Interruptible waits

---

## Phase 5: API Server

### 5.1 FastAPI Backend
- [ ] API routes structure
- [ ] Workflow CRUD endpoints
- [ ] Execution endpoints
- [ ] WebSocket for live logs

### 5.2 Background Runner
- [ ] `flowpilot serve` command
- [ ] Daemon mode (--daemon)
- [ ] launchd plist generation
- [ ] Graceful shutdown

---

## Phase 6: Frontend

### 6.1 Project Setup
- [ ] Vite + React + TypeScript
- [ ] shadcn/ui components
- [ ] TanStack Query setup
- [ ] Zustand store

### 6.2 Core Views
- [ ] Workflow list page
- [ ] Workflow editor (Monaco)
- [ ] Execution history
- [ ] Live log viewer

### 6.3 Flow Visualization
- [ ] React Flow integration
- [ ] YAML to flow conversion
- [ ] Node status indicators
- [ ] Execution animation

### 6.4 Polish
- [ ] Dark mode (default)
- [ ] Keyboard shortcuts
- [ ] Error handling UI
- [ ] Loading states

---

## Phase 7: Distribution

### 7.1 Packaging
- [ ] Frontend build embedding
- [ ] PyPI package
- [ ] Version management

### 7.2 Installation Experience
- [ ] `pip install flowpilot`
- [ ] First-run setup
- [ ] Configuration wizard

### 7.3 Documentation
- [ ] User guide
- [ ] Node reference
- [ ] Example workflows

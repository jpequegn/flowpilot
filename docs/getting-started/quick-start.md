# Quick Start Guide

This guide will help you create and run your first FlowPilot workflow in under 5 minutes.

## Step 1: Initialize a Project

Create a new FlowPilot project:

```bash
# Create a project directory
mkdir my-workflows
cd my-workflows

# Initialize FlowPilot
flowpilot init
```

This creates the following structure:

```
my-workflows/
├── flowpilot.db        # SQLite database for execution history
└── workflows/          # Directory for workflow YAML files
    └── example.yaml    # Example workflow
```

## Step 2: Explore the Example Workflow

FlowPilot creates an example workflow during initialization:

```yaml
# workflows/example.yaml
name: example-workflow
description: A simple example workflow

triggers:
  - type: manual

nodes:
  - id: step1
    type: shell
    config:
      command: echo "Hello from FlowPilot!"

  - id: step2
    type: shell
    config:
      command: echo "Current time: $(date)"
    depends_on:
      - step1
```

## Step 3: Run the Workflow

Execute the workflow from the command line:

```bash
# Run by workflow name
flowpilot run example

# Or specify the full path
flowpilot run workflows/example.yaml
```

You'll see output like:

```
Running workflow: example-workflow
Executing node: step1
Hello from FlowPilot!
Executing node: step2
Current time: Wed Dec 18 10:30:00 PST 2024
Workflow completed successfully
```

## Step 4: Start the Web UI

For a visual interface, start the server:

```bash
flowpilot serve
```

Open http://localhost:8080 in your browser to:

- View all workflows
- Run workflows manually
- Monitor execution in real-time
- View execution history and logs

## Step 5: Create Your Own Workflow

Create a new workflow file:

```yaml
# workflows/backup.yaml
name: backup-notes
description: Backup notes directory

triggers:
  - type: manual
  - type: cron
    schedule: "0 9 * * *"  # Daily at 9 AM

nodes:
  - id: create-backup-dir
    type: shell
    config:
      command: mkdir -p ~/backups/notes

  - id: copy-files
    type: shell
    config:
      command: cp -r ~/Documents/notes/* ~/backups/notes/
    depends_on:
      - create-backup-dir

  - id: log-completion
    type: log
    config:
      message: "Backup completed at {{ now() }}"
      level: info
    depends_on:
      - copy-files
```

Run your new workflow:

```bash
flowpilot run backup
```

## Key Concepts

### Workflows
A workflow is a collection of nodes that execute in a defined order. Workflows are defined in YAML files.

### Nodes
Nodes are individual steps in a workflow. Each node has:
- **id** - Unique identifier
- **type** - The operation type (shell, http, file, etc.)
- **config** - Type-specific configuration
- **depends_on** - List of nodes that must complete first

### Triggers
Triggers define when a workflow runs:
- **manual** - Run on demand
- **cron** - Run on a schedule
- **file-watch** - Run when files change

### Templating
Use `{{ expression }}` for dynamic values:

```yaml
- id: greet
  type: shell
  config:
    command: echo "Hello {{ env('USER') }}!"
```

## Next Steps

- [Workflow Syntax](../guides/workflow-syntax.md) - Complete workflow reference
- [Node Types](../nodes/) - All available node types
- [Templating](../guides/templating.md) - Dynamic expressions
- [Examples](../examples/) - More workflow examples

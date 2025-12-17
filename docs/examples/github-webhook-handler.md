# GitHub Webhook Handler

Process GitHub webhook events to automate repository tasks.

## Overview

This workflow handles GitHub webhook events to:
1. Detect event type (push, PR, issue)
2. Route to appropriate handler
3. Perform automated actions

## Workflow

```yaml
name: github-webhook-handler
description: Process GitHub webhook events

triggers:
  - type: webhook
    path: /webhooks/github

nodes:
  - id: log-event
    type: log
    config:
      message: "Received GitHub event: {{ input.headers['X-GitHub-Event'] }}"
      level: info

  - id: parse-event
    type: shell
    config:
      command: |
        echo '{{ input.body | tojson }}' | jq -r '.action // "none"'
    depends_on:
      - log-event

  - id: route-event
    type: condition
    config:
      expression: "{{ input.headers['X-GitHub-Event'] == 'push' }}"
      then_branch: handle-push
      else_branch: check-pr
    depends_on:
      - parse-event

  # Push event handler
  - id: handle-push
    type: shell
    config:
      command: |
        echo "Push to {{ input.body.ref }} by {{ input.body.pusher.name }}"
        echo "Commits: {{ input.body.commits | length }}"

  - id: notify-push
    type: http
    config:
      url: "{{ env('SLACK_WEBHOOK_URL') }}"
      method: POST
      body:
        text: |
          🚀 New push to {{ input.body.repository.full_name }}
          Branch: {{ input.body.ref | replace('refs/heads/', '') }}
          By: {{ input.body.pusher.name }}
          Commits: {{ input.body.commits | length }}
    depends_on:
      - handle-push

  # PR event handler
  - id: check-pr
    type: condition
    config:
      expression: "{{ input.headers['X-GitHub-Event'] == 'pull_request' }}"
      then_branch: handle-pr
      else_branch: check-issue

  - id: handle-pr
    type: shell
    config:
      command: |
        echo "PR #{{ input.body.pull_request.number }}: {{ input.body.action }}"
        echo "Title: {{ input.body.pull_request.title }}"

  - id: auto-label-pr
    type: http
    config:
      url: "{{ input.body.pull_request.issue_url }}/labels"
      method: POST
      headers:
        Authorization: "Bearer {{ env('GITHUB_TOKEN') }}"
        Accept: application/vnd.github.v3+json
      body:
        labels:
          - needs-review
    condition: "{{ input.body.action == 'opened' }}"
    depends_on:
      - handle-pr

  # Issue event handler
  - id: check-issue
    type: condition
    config:
      expression: "{{ input.headers['X-GitHub-Event'] == 'issues' }}"
      then_branch: handle-issue
      else_branch: unhandled-event

  - id: handle-issue
    type: shell
    config:
      command: |
        echo "Issue #{{ input.body.issue.number }}: {{ input.body.action }}"
        echo "Title: {{ input.body.issue.title }}"

  - id: auto-respond-issue
    type: http
    config:
      url: "{{ input.body.issue.comments_url }}"
      method: POST
      headers:
        Authorization: "Bearer {{ env('GITHUB_TOKEN') }}"
        Accept: application/vnd.github.v3+json
      body:
        body: |
          Thanks for opening this issue! Our team will review it shortly.

          In the meantime, please make sure you've:
          - [ ] Searched for existing issues
          - [ ] Provided reproduction steps
          - [ ] Included relevant logs or screenshots
    condition: "{{ input.body.action == 'opened' }}"
    depends_on:
      - handle-issue

  - id: unhandled-event
    type: log
    config:
      message: "Unhandled event type: {{ input.headers['X-GitHub-Event'] }}"
      level: warning
```

## Setup

### Environment Variables

```bash
export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/xxx"
```

### GitHub Webhook Configuration

1. Go to your repository Settings → Webhooks
2. Add webhook:
   - Payload URL: `http://your-server:8080/webhooks/github`
   - Content type: `application/json`
   - Events: Select events to receive

### Exposing FlowPilot

For development, use ngrok:

```bash
ngrok http 8080
# Use the ngrok URL in GitHub webhook settings
```

## Customization

### Add CI/CD Trigger

```yaml
- id: trigger-ci
  type: http
  config:
    url: "https://api.github.com/repos/{{ input.body.repository.full_name }}/actions/workflows/ci.yml/dispatches"
    method: POST
    headers:
      Authorization: "Bearer {{ env('GITHUB_TOKEN') }}"
      Accept: application/vnd.github.v3+json
    body:
      ref: "{{ input.body.ref }}"
  condition: "{{ input.headers['X-GitHub-Event'] == 'push' }}"
```

### Validate Webhook Signature

```yaml
- id: validate-signature
  type: shell
  config:
    command: |
      EXPECTED=$(echo -n '{{ input.body | tojson }}' | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print "sha256="$2}')
      RECEIVED="{{ input.headers['X-Hub-Signature-256'] }}"
      if [ "$EXPECTED" = "$RECEIVED" ]; then
        echo "valid"
      else
        echo "invalid"
        exit 1
      fi
```

## Security Notes

- Always validate webhook signatures
- Use HTTPS in production
- Store tokens securely
- Limit webhook permissions to necessary events

## Related Examples

- [Daily Code Review](daily-code-review.md) - Automated PR reviews

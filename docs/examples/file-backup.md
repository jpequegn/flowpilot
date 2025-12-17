# File Backup

Automated backup system for important directories with rotation.

## Overview

This workflow:
1. Creates timestamped backups of specified directories
2. Compresses backups to save space
3. Uploads to cloud storage (optional)
4. Cleans up old backups

## Workflow

```yaml
name: file-backup
description: Automated backup with rotation

triggers:
  - type: cron
    schedule: "0 2 * * *"  # Daily at 2 AM
  - type: manual

nodes:
  - id: setup
    type: shell
    config:
      command: |
        BACKUP_DIR="${HOME}/backups"
        TIMESTAMP=$(date +%Y%m%d-%H%M%S)
        mkdir -p "$BACKUP_DIR"
        echo "$BACKUP_DIR" > /tmp/backup_dir
        echo "$TIMESTAMP" > /tmp/backup_timestamp

  - id: log-start
    type: log
    config:
      message: "Starting backup at {{ now() }}"
      level: info
    depends_on:
      - setup

  - id: backup-documents
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        TIMESTAMP=$(cat /tmp/backup_timestamp)
        SOURCE="${HOME}/Documents"
        DEST="$BACKUP_DIR/documents-$TIMESTAMP.tar.gz"

        if [ -d "$SOURCE" ]; then
          tar -czf "$DEST" -C "$(dirname $SOURCE)" "$(basename $SOURCE)"
          echo "Created: $DEST"
          ls -lh "$DEST"
        else
          echo "Source not found: $SOURCE"
        fi
    depends_on:
      - setup

  - id: backup-projects
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        TIMESTAMP=$(cat /tmp/backup_timestamp)
        SOURCE="${HOME}/Projects"
        DEST="$BACKUP_DIR/projects-$TIMESTAMP.tar.gz"

        if [ -d "$SOURCE" ]; then
          # Exclude node_modules, .git, etc.
          tar -czf "$DEST" \
            --exclude='node_modules' \
            --exclude='.git' \
            --exclude='*.pyc' \
            --exclude='__pycache__' \
            -C "$(dirname $SOURCE)" "$(basename $SOURCE)"
          echo "Created: $DEST"
          ls -lh "$DEST"
        else
          echo "Source not found: $SOURCE"
        fi
    depends_on:
      - setup

  - id: backup-config
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        TIMESTAMP=$(cat /tmp/backup_timestamp)
        DEST="$BACKUP_DIR/config-$TIMESTAMP.tar.gz"

        # Backup dotfiles and configs
        tar -czf "$DEST" \
          -C "$HOME" \
          .zshrc .bashrc .gitconfig .ssh/config \
          2>/dev/null || true

        echo "Created: $DEST"
        ls -lh "$DEST"
    depends_on:
      - setup

  - id: wait-for-backups
    type: delay
    config:
      seconds: 1
    depends_on:
      - backup-documents
      - backup-projects
      - backup-config

  - id: calculate-size
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        TIMESTAMP=$(cat /tmp/backup_timestamp)
        du -sh "$BACKUP_DIR"/*-$TIMESTAMP.tar.gz 2>/dev/null || echo "No backups found"
    depends_on:
      - wait-for-backups

  - id: cleanup-old
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        KEEP_DAYS=7

        echo "Cleaning up backups older than $KEEP_DAYS days..."

        find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$KEEP_DAYS -exec rm -v {} \;

        echo "Remaining backups:"
        ls -la "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "No backups found"
    depends_on:
      - calculate-size

  - id: disk-usage
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        echo "Total backup size:"
        du -sh "$BACKUP_DIR"
    depends_on:
      - cleanup-old

  - id: log-complete
    type: log
    config:
      message: "Backup completed successfully"
      level: info
    depends_on:
      - disk-usage
```

## Advanced: Cloud Upload

Add S3 upload capability:

```yaml
  - id: upload-to-s3
    type: shell
    config:
      command: |
        BACKUP_DIR=$(cat /tmp/backup_dir)
        TIMESTAMP=$(cat /tmp/backup_timestamp)
        BUCKET="{{ env('S3_BUCKET') }}"

        for file in "$BACKUP_DIR"/*-$TIMESTAMP.tar.gz; do
          if [ -f "$file" ]; then
            aws s3 cp "$file" "s3://$BUCKET/backups/$(basename $file)"
            echo "Uploaded: $file"
          fi
        done
    condition: "{{ env('S3_BUCKET') != '' }}"
    depends_on:
      - wait-for-backups
```

## Configuration

### Environment Variables

```bash
# Optional: for S3 upload
export S3_BUCKET="my-backup-bucket"
export AWS_ACCESS_KEY_ID="xxx"
export AWS_SECRET_ACCESS_KEY="xxx"
```

### Customization

**Backup different directories:**

Edit the `backup-*` nodes to target your directories.

**Change retention period:**

Modify `KEEP_DAYS=7` in the cleanup node.

**Change schedule:**

Modify the cron expression:
- `0 2 * * *` - Daily at 2 AM
- `0 */6 * * *` - Every 6 hours
- `0 2 * * 0` - Weekly on Sunday

## Running Manually

```bash
# Run backup immediately
flowpilot run file-backup --verbose

# Check backup directory
ls -la ~/backups/
```

## Monitoring

Add notification on failure:

```yaml
  - id: notify-failure
    type: http
    config:
      url: "{{ env('SLACK_WEBHOOK') }}"
      method: POST
      body:
        text: "⚠️ Backup failed at {{ now() }}"
    condition: |
      {{
        nodes.backup-documents.status == 'failed' or
        nodes.backup-projects.status == 'failed'
      }}
```

## Best Practices

1. **Test restores regularly** - A backup is useless if you can't restore
2. **Use compression** - Save space with tar.gz
3. **Exclude unnecessary files** - Skip node_modules, .git, caches
4. **Rotate backups** - Don't keep backups forever
5. **Store offsite** - Use cloud storage for disaster recovery
6. **Monitor failures** - Set up notifications

## Related Examples

- [Data Processing Pipeline](data-pipeline.md) - More complex data workflows

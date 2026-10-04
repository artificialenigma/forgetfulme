#!/bin/sh
set -eu
umask 077
interval="${BACKUP_INTERVAL_SECONDS:-86400}"
retention="${BACKUP_RETENTION_DAYS:-14}"
case "$interval" in ''|*[!0-9]*) exit 1;; esac
case "$retention" in ''|*[!0-9]*) exit 1;; esac
[ "$interval" -ge 60 ] && [ "$retention" -ge 1 ]
mkdir -p /backups
while :; do
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    staging="/backups/.pending-$stamp"
    mkdir "$staging"
    if pg_dump --format=custom --file="$staging/database.dump" && tar -czf "$staging/content.tar.gz" -C /data/content . && tar -czf "$staging/vault.tar.gz" -C /vault . && tar -czf "$staging/obsidian-config.tar.gz" -C /obsidian-config . && pg_restore --list "$staging/database.dump" >/dev/null; then
        mv "$staging" "/backups/$stamp"
        date -u +%s > /backups/last-success
        find /backups -mindepth 1 -maxdepth 1 -type d ! -name '.pending-*' -mtime +"$retention" -exec rm -rf {} +
        echo "Backup completed: $stamp"
    else
        rm -rf "$staging"
        echo "Backup failed; retrying in 60 seconds" >&2
        sleep 60
        continue
    fi
    sleep "$interval"
done

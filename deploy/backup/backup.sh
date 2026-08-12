#!/bin/sh
set -eu

: "${MYSQL_HOST:?}" "${MYSQL_USER:?}" "${MYSQL_PASSWORD:?}" "${MYSQL_DB:?}" "${BACKUP_ENCRYPTION_KEY:?}" "${BACKUP_REMOTE:?}"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
file="/tmp/${MYSQL_DB}-${stamp}.sql.gz.enc"

mysqldump -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" --single-transaction --routines --events "$MYSQL_DB" \
  | gzip \
  | openssl enc -aes-256-cbc -salt -pbkdf2 -pass env:BACKUP_ENCRYPTION_KEY -out "$file"

rclone copy "$file" "$BACKUP_REMOTE/daily"
touch /tmp/backup-heartbeat
rclone delete "$BACKUP_REMOTE/daily" --min-age 7d
if [ "$(date -u +%u)" = "7" ]; then
  rclone copy "$file" "$BACKUP_REMOTE/weekly"
  rclone delete "$BACKUP_REMOTE/weekly" --min-age 28d
fi
rm -f "$file"

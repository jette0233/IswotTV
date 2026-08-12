#!/bin/sh
set -eu
: "${MYSQL_HOST:?}" "${MYSQL_USER:?}" "${MYSQL_PASSWORD:?}" "${MYSQL_DB:?}" "${BACKUP_ENCRYPTION_KEY:?}"
: "${1:?usage: restore.sh encrypted-backup.sql.gz.enc}"

openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_ENCRYPTION_KEY -in "$1" \
  | gzip -d \
  | mysql -h "$MYSQL_HOST" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DB"

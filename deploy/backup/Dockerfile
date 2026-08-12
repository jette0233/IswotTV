FROM alpine:3.21
RUN apk add --no-cache mariadb-client openssl rclone tzdata
COPY backup.sh restore.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh
CMD ["sh", "-c", "while true; do /usr/local/bin/backup.sh; sleep 86400; done"]

import os
import uuid

import pytest
import pymysql
import redis

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="integration services not enabled"),
]


def test_migrated_schema_has_idempotency_constraints():
    connection = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "chaoxing"), password=os.getenv("MYSQL_PASSWORD", "testpass"),
        database=os.getenv("MYSQL_DB", "chaoxing"),
    )
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = {row[0] for row in cursor.fetchall()}
            assert {"sign_activities", "sign_tasks", "outbox_events", "refresh_tokens"} <= tables
            cursor.execute("SHOW INDEX FROM sign_tasks WHERE Key_name = 'uk_task_activity_user'")
            assert len(cursor.fetchall()) == 2
    finally:
        connection.close()


def test_redis_consumer_group_tracks_and_acks_pending_message():
    client = redis.Redis(host=os.getenv("REDIS_HOST", "127.0.0.1"), port=int(os.getenv("REDIS_PORT", "6379")), decode_responses=True)
    stream = f"test:sign:{uuid.uuid4().hex}"
    group = "workers"
    try:
        client.xgroup_create(stream, group, id="0", mkstream=True)
        client.xadd(stream, {"activity_id": "1", "user_id": "1"})
        rows = client.xreadgroup(group, "worker-1", {stream: ">"}, count=1)
        message_id = rows[0][1][0][0]
        assert client.xpending(stream, group)["pending"] == 1
        assert client.xack(stream, group, message_id) == 1
        assert client.xpending(stream, group)["pending"] == 0
    finally:
        client.delete(stream)

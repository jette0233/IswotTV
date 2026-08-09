"""
Redis Stream 消息队列管理器

按course_id隔离MQ:
- mq:{course_id}:stream  → Redis Stream，存储enc消息
- mq:{course_id}:producer → 当前生产者信息（选举制）
- mq:{course_id}:ttl     → TTL标记，MQ活跃时长

MQ生命周期:
- 第一个有效enc推入时创建 → 设置20min TTL
- TTL到期自动删除
- 一个course同时只有1个MQ
"""

import json
import time
import threading
from datetime import datetime, timezone
from flask import current_app


class MQManager:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._local_producers = {}  # 本地缓存：course_id -> producer_uid

    # ─────────── 生产者选举 ───────────

    def claim_producer(self, course_id, user_id):
        """
        竞选生产者。先到先得，心跳超时15s自动让出。
        返回: (success: bool, msg: str)
        """
        producer_key = f"mq:{course_id}:producer"
        now = time.time()

        # 用Redis SET NX实现先到先得
        if not self.redis.exists(producer_key):
            self.redis.hset(producer_key, mapping={
                "uid": str(user_id),
                "claimed_at": now,
                "last_heartbeat": now,
            })
            self.redis.expire(producer_key, 30)  # 30s整体过期保底
            return True, "竞选成功"

        # 检查当前生产者是否超时
        producer_data = self.redis.hgetall(producer_key)
        if not producer_data:
            return False, "竞选失败，请重试"

        last_hb = float(producer_data.get(b"last_heartbeat", producer_data.get("last_heartbeat", 0)))
        timeout = current_app.config.get("PRODUCER_HEARTBEAT_TIMEOUT", 15)

        if time.time() - last_hb > timeout:
            # 超时，抢占
            self.redis.hset(producer_key, mapping={
                "uid": str(user_id),
                "claimed_at": now,
                "last_heartbeat": now,
            })
            self.redis.expire(producer_key, 30)
            return True, "抢占成功（上一生产者已超时）"

        current_uid = producer_data.get(b"uid", producer_data.get("uid", b"0")).decode() if isinstance(
            producer_data.get(b"uid", producer_data.get("uid", b"0")), bytes) else producer_data.get("uid", "0")
        return False, f"当前生产者是用户{current_uid}"

    def heartbeat(self, course_id, user_id):
        """生产者心跳"""
        producer_key = f"mq:{course_id}:producer"
        producer_data = self.redis.hgetall(producer_key)
        if not producer_data:
            return False, "无活跃生产者"

        current_uid = producer_data.get(b"uid", producer_data.get("uid", b"0"))
        if isinstance(current_uid, bytes):
            current_uid = current_uid.decode()
        if str(current_uid) != str(user_id):
            return False, "你不是当前生产者"

        self.redis.hset(producer_key, "last_heartbeat", time.time())
        self.redis.expire(producer_key, 30)
        return True, "心跳成功"

    def get_current_producer(self, course_id):
        """查看当前生产者"""
        producer_key = f"mq:{course_id}:producer"
        data = self.redis.hgetall(producer_key)
        if not data:
            return None
        uid = data.get(b"uid", data.get("uid", None))
        if isinstance(uid, bytes):
            uid = uid.decode()
        return uid

    # ─────────── 消息队列 ───────────

    def push_enc(self, course_id, enc, active_id, latitude=None, longitude=None):
        """
        推enc到MQ。如果MQ不存在则自动创建（并设置TTL）。
        返回: (success: bool, is_new: bool)
        """
        stream_key = f"mq:{course_id}:stream"
        ttl_key = f"mq:{course_id}:ttl"

        is_new = False
        if not self.redis.exists(stream_key):
            is_new = True

        msg_data = {
            "enc": enc,
            "active_id": str(active_id),
            "pushed_at": str(time.time()),
        }
        if latitude is not None:
            msg_data["latitude"] = str(latitude)
        if longitude is not None:
            msg_data["longitude"] = str(longitude)

        msg_id = self.redis.xadd(stream_key, msg_data, maxlen=100)

        # 首次创建时设置TTL
        if is_new:
            ttl = current_app.config.get("MQ_TTL_SECONDS", 1200)
            self.redis.expire(stream_key, ttl)
            self.redis.setex(ttl_key, ttl, "1")

        return True, is_new

    def get_latest_enc(self, course_id):
        """
        取出MQ中最新的enc。
        返回: dict 或 None
        """
        stream_key = f"mq:{course_id}:stream"
        if not self.redis.exists(stream_key):
            return None

        # 用XRANGE按时间倒序取最新一条
        results = self.redis.xrevrange(stream_key, max="+", min="-", count=1)
        if not results:
            return None

        msg_id, data = results[0]
        def _get(k):
            v = data.get(k.encode() if isinstance(k, str) else k, data.get(k, ""))
            if isinstance(v, bytes): v = v.decode()
            return v

        return {
            "msg_id": _get("msg_id"),
            "enc": _get("enc"),
            "active_id": _get("active_id"),
            "latitude": _get("latitude") or None,
            "longitude": _get("longitude") or None,
            "pushed_at": _get("pushed_at"),
        }

    def course_has_active_mq(self, course_id):
        """检查课程是否有活跃MQ"""
        stream_key = f"mq:{course_id}:stream"
        return self.redis.exists(stream_key) > 0

    def get_mq_ttl(self, course_id):
        """查看MQ剩余存活时间（秒）"""
        stream_key = f"mq:{course_id}:stream"
        ttl = self.redis.ttl(stream_key)
        return max(0, ttl)

    def destroy_mq(self, course_id):
        """手动销毁MQ"""
        keys = [
            f"mq:{course_id}:stream",
            f"mq:{course_id}:producer",
            f"mq:{course_id}:ttl",
        ]
        for k in keys:
            self.redis.delete(k)


# 全局单例
mq_manager = MQManager()

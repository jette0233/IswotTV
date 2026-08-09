"""
消费者自动签到守护服务 — 在Flask后台持久化运行

逻辑：
1. 每5秒扫描一次数据库，查所有启用了自动签到的用户
2. 对每个用户，查其加入的课程中哪些有活跃MQ
3. 有enc且未签到 → 调stuSignajax签到
4. 记录结果到sign_logs
"""

import time
import re
import json
import os
import base64
import requests as http_requests
from datetime import datetime, timezone
from flask import current_app
from app.models.models import db, User, Course, SignLog
from app.services.mq_manager import mq_manager
from app.services.geo_convert import wgs84_to_gcj02


class AutoSignerService:
    def __init__(self):
        self._enabled = False
        self._thread = None
        self._signed_cache = set()  # (uid, enc) 已签过的组合

    def start(self, app):
        """启动后台签到守护线程"""
        self._enabled = True
        self._app = app
        import threading
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print("[AutoSigner] 消费者守护线程已启动")

    def stop(self):
        self._enabled = False

    def _loop(self):
        while self._enabled:
            try:
                with self._app.app_context():
                    self._tick()
            except Exception as e:
                print(f"[AutoSigner] 错误: {e}")
            time.sleep(5)

    def _tick(self):
        """一次扫描周期"""
        # 查询所有有 Cookie 的用户（auto模式或manual模式，Cookie未过期）
        now = datetime.utcnow()
        users = User.query.filter(
            User.cookie_manual.isnot(None),
            User.cookie_manual != "",
            (User.cookie_expire_at.is_(None) | (User.cookie_expire_at > now)),
        ).all()

        for user in users:
            try:
                self._process_user(user)
            except Exception as e:
                print(f"[AutoSigner] 用户{user.id}处理失败: {e}")

    def _process_user(self, user):
        """处理单个用户的签到"""
        # 查该用户加入的所有课程
        from app.models.models import CourseMember
        memberships = CourseMember.query.filter_by(user_id=user.id).all()

        for member in memberships:
            course_id = member.course_id

            # 该课程是否有活跃MQ
            if not mq_manager.course_has_active_mq(course_id):
                continue

            # 取最新enc
            latest = mq_manager.get_latest_enc(course_id)
            if not latest or not latest.get("enc"):
                continue

            enc = latest["enc"]
            active_id = latest["active_id"]
            cache_key = (user.id, enc)

            # 已签过就跳过
            if cache_key in self._signed_cache:
                continue

            # 查课程信息
            course = Course.query.get(course_id)
            if not course:
                continue

            # 课程有防作弊验证 → 跳过
            if course.has_captcha:
                print(f"[AutoSigner] 课程{course_id}({course.course_name}) 启用了防作弊验证，跳过（请在学习通APP完成签到）")
                log = SignLog(
                    user_id=user.id, course_id=course_id,
                    active_id=active_id, enc=enc,
                    status="skipped", message="该课程有防作弊验证，请在学习通APP完成签到",
                )
                db.session.add(log)
                db.session.commit()
                self._signed_cache.add(cache_key)
                continue

            from_mq_lat = latest.get("latitude")
            from_mq_lng = latest.get("longitude")
            lat = course.default_latitude if course.default_latitude else (from_mq_lat or "-1")
            lng = course.default_longitude if course.default_longitude else (from_mq_lng or "-1")

            course_addr = course.address if course.address else ""
            if not course_addr and lat != "-1" and lng != "-1":
                from app.services.baidu_geo import reverse_geocode
                addr = reverse_geocode(float(lng), float(lat))
                if addr:
                    course_addr = addr

            print(f"[AutoSigner] 课程{course_id} enc={enc[:16]}... lat={lat} lng={lng}")

            # 直接调签到（不做滑块验证重试）
            result_text, status, message = self._do_sign(
                cookie=user.cookie_manual,
                enc=enc,
                active_id=active_id,
                latitude=lat or "-1",
                longitude=lng or "-1",
                address=course_addr,
            )

            # 记录日志
            log = SignLog(
                user_id=user.id,
                course_id=course_id,
                active_id=active_id,
                enc=enc,
                status=status,
                message=message,
            )
            db.session.add(log)
            db.session.commit()

            # 缓存已签enc
            if status == "success":
                self._signed_cache.add(cache_key)
                print(f"[AutoSigner] 用户{user.id} 课程{course.course_name} 签到成功")
            elif "需要滑块验证" in message:
                self._signed_cache.add(cache_key)
                print(f"[AutoSigner] 用户{user.id} 课程{course.course_name} 需要滑块验证，请在手机端学习通APP完成签到")
                # 自动标记该课程有验证码
                if not course.has_captcha:
                    course.has_captcha = True
                    db.session.commit()
                    print(f"[AutoSigner] 课程{course.course_name} 已自动标记为 has_captcha=True")
            elif "Cookie" in message:
                print(f"[AutoSigner] 用户{user.id} Cookie失效")

            # 限制缓存大小
            if len(self._signed_cache) > 5000:
                self._signed_cache.clear()

    def _do_sign(self, cookie, enc, active_id, latitude=None, longitude=None, validate=None, address=""):
        """执行签到 — 一次性带上完整参数（uid/name/fid/deviceCode + 可选 location JSON）"""
        lat = latitude or "-1"
        lng = longitude or "-1"
        if lat != "-1" and lng != "-1":
            try:
                gcj_lng, gcj_lat = wgs84_to_gcj02(float(lng), float(lat))
                lat, lng = str(gcj_lat), str(gcj_lng)
            except:
                pass

        # 提取 Cookie 信息
        uid_match = re.search(r'_uid=(\d+)', cookie)
        pk_uid = uid_match.group(1) if uid_match else ""
        uname_match = re.search(r'uname="([^"]*)"', cookie)
        pk_name = uname_match.group(1) if uname_match else ""
        fid_match = re.search(r'spaceFid=(\d+)', cookie)
        pk_fid = fid_match.group(1) if fid_match else "0"
        device_code = base64.b64encode(os.urandom(48)).decode()

        sign_url = "https://mobilelearn.chaoxing.com/pptSign/stuSignajax"

        # 基础参数：uid/name/fid/deviceCode 每次都带
        params = {
            "activeId": active_id,
            "enc": enc,
            "uid": pk_uid,
            "name": pk_name,
            "fid": pk_fid,
            "deviceCode": device_code,
            "clientip": "",
            "latitude": "-1",
            "longitude": "-1",
            "appType": "15",
            "address": address or "",
        }
        if validate:
            params["validate"] = validate

        # 有 GPS → 附加 location JSON
        if lat != "-1" and lng != "-1":
            location = {
                "result": 1,
                "latitude": lat,
                "longitude": lng,
                "address": address or "",
                "mockData": '{"strategy":0,"probability":-1}',
            }
            params["location"] = json.dumps(location, ensure_ascii=False)

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
            ),
            "Cookie": cookie,
            "Referer": "https://mobilelearn.chaoxing.com/",
        }

        try:
            resp = http_requests.get(sign_url, params=params, headers=headers, timeout=10)
            text = resp.text.strip()

            # ─── errorLocation1 降级 ───
            if "errorLocation1" in text:
                # 方案1: 去掉 location JSON，直接传 top-level lat/lng
                print(f"[AutoSigner] errorLocation1，尝试降级方案1（top-level lat/lng）...")
                params.pop("location", None)
                params["latitude"] = lat if lat != "-1" else "39.9042"
                params["longitude"] = lng if lng != "-1" else "116.4074"
                resp2 = http_requests.get(sign_url, params=params, headers=headers, timeout=10)
                text = resp2.text.strip()
                print(f"[AutoSigner] 降级方案1结果: {text[:80]}")

            if "errorLocation1" in text:
                # 方案2: 去掉 enc，加 ifTiJiao=1
                print(f"[AutoSigner] errorLocation1 仍存在，尝试方案2（name+uid+ifTiJiao）...")
                fallback = {
                    "name": pk_name, "address": address or "", "activeId": active_id,
                    "uid": pk_uid, "clientip": "",
                    "latitude": lat if lat != "-1" else "39.9042",
                    "longitude": lng if lng != "-1" else "116.4074",
                    "fid": pk_fid, "appType": "15", "ifTiJiao": "1",
                }
                resp2 = http_requests.get(sign_url, params=fallback, headers=headers, timeout=10)
                text = resp2.text.strip()
                print(f"[AutoSigner] 降级方案2结果: {text[:80]}")

            if "success" in text.lower():
                return text, "success", "签到成功"
            elif "已签到" in text or "签到过了" in text:
                return text, "success", "已签到"
            elif "validate" in text.lower():
                return text, "fail", f"需要滑块验证: {text[:50]}"
            elif "errorLocation1" in text:
                return text, "fail", f"定位失败(errorLocation1): {text[:50]}"
            elif "请登录" in text:
                return text, "fail", "Cookie已失效"
            else:
                return text, "fail", f"签到失败: {text[:100]}"
        except Exception as e:
            return str(e), "fail", f"网络错误: {str(e)}"


auto_signer = AutoSignerService()

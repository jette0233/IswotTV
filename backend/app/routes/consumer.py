import re
import json
import os
import base64
import requests as http_requests
from flask import Blueprint, request, jsonify, current_app
from app.models.models import db, User, Course, CourseMember, SignLog
from app.services.mq_manager import mq_manager
from app.services.geo_convert import wgs84_to_gcj02
from datetime import datetime, timezone

consumer_bp = Blueprint("consumer", __name__)


def get_user_cookie(user):
    if user.cookie_manual:
        return user.cookie_manual
    return None


def _extract_cookie_info(cookie, user=None):
    """从Cookie中提取 uid, name, fid, deviceCode"""
    uid_match = re.search(r'_uid=(\d+)', cookie)
    pk_uid = uid_match.group(1) if uid_match else ""
    uname_match = re.search(r'uname="([^"]*)"', cookie)
    pk_name = uname_match.group(1) if uname_match else (user.phone if user else "")
    fid_match = re.search(r'spaceFid=(\d+)', cookie)
    pk_fid = fid_match.group(1) if fid_match else "0"
    # 生成稳定的 deviceCode（per session）
    device_code = base64.b64encode(os.urandom(48)).decode()
    return pk_uid, pk_name, pk_fid, device_code


def _build_sign_params(active_id, enc, address, pk_uid, pk_name, pk_fid, device_code, lat_str="-1", lng_str="-1"):
    """
    构造 stuSignajax 完整参数集。
    定位签到的关键：uid/name/fid/deviceCode 每次都带上，
    有 GPS 时通过 location JSON 传入，而非靠 errorLocation1 降级。
    """
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
    # 有有效 GPS → 附加 location JSON
    if lat_str and lng_str and lat_str != "-1" and lng_str != "-1":
        location = {
            "result": 1,
            "latitude": lat_str,
            "longitude": lng_str,
            "address": address or "",
            "mockData": '{"strategy":0,"probability":-1}',
        }
        params["location"] = json.dumps(location, ensure_ascii=False)
    return params


@consumer_bp.route("/check-sign", methods=["GET"])
def check_sign():
    """
    消费者轮询接口：检查指定课程是否有可签到的活动
    如果有active MQ + 最新enc，返回enc供客户端调用签到
    """
    course_id = request.args.get("course_id")
    uid = request.args.get("uid")

    if not course_id or not uid:
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    # 验证用户是该课程成员
    member = CourseMember.query.filter_by(user_id=uid, course_id=course_id).first()
    if not member:
        return jsonify({"code": 403, "msg": "你不是该课程成员"}), 403

    # 检查是否有活跃MQ
    if not mq_manager.course_has_active_mq(course_id):
        return jsonify({"code": 200, "data": {"has_activity": False, "msg": "暂无签到活动"}})

    # 获取最新enc
    latest = mq_manager.get_latest_enc(course_id)
    if not latest:
        return jsonify({"code": 200, "data": {"has_activity": True, "has_enc": False, "msg": "等待enc中"}})

    return jsonify({
        "code": 200,
        "data": {
            "has_activity": True,
            "has_enc": True,
            "enc": latest["enc"],
            "active_id": latest["active_id"],
        }
    })


@consumer_bp.route("/do-sign", methods=["POST"])
def do_sign():
    """
    服务端代签：由服务器代替用户调用学习通签到API
    用户只需提供cookie，由服务器统一调用stuSignajax
    """
    data = request.get_json(force=True, silent=True) or {}
    uid = data.get("uid")
    course_id = data.get("course_id")
    enc = data.get("enc")

    if not all([uid, course_id, enc]):
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    cookie = get_user_cookie(user)
    if not cookie:
        return jsonify({"code": 400, "msg": "用户未配置Cookie，请先上传"}), 400

    latest = mq_manager.get_latest_enc(course_id)
    if not latest:
        return jsonify({"code": 400, "msg": "该课程暂无签到活动或活动已结束"}), 400

    active_id = latest["active_id"]
    course = Course.query.get(course_id)

    # 提取 Cookie 中的 uid/name/fid/deviceCode
    pk_uid, pk_name, pk_fid, device_code = _extract_cookie_info(cookie, user)

    # 定位参数优先级: 课程默认值 > MQ实时值
    lat = course.default_latitude if (course and course.default_latitude) else (latest.get("latitude") or "-1")
    lng = course.default_longitude if (course and course.default_longitude) else (latest.get("longitude") or "-1")

    # 地址: 课程设置 > 百度反向地理编码 > 空
    course_addr = course.address if (course and course.address) else ""
    if not course_addr and lat != "-1" and lng != "-1":
        from app.services.baidu_geo import reverse_geocode
        addr = reverse_geocode(float(lng), float(lat))
        if addr:
            course_addr = addr

    # WGS84 → GCJ02 转换
    gcj_lat, gcj_lng = lat, lng
    if lat != "-1" and lng != "-1":
        try:
            gcj_lng, gcj_lat = wgs84_to_gcj02(float(lng), float(lat))
            gcj_lat, gcj_lng = str(gcj_lat), str(gcj_lng)
        except:
            pass

    sign_url = current_app.config["CHAOXING_SIGN_URL"]

    # ─── 第一次请求: 一次性带上全部参数 ───
    params = _build_sign_params(active_id, enc, course_addr,
                                pk_uid, pk_name, pk_fid, device_code,
                                gcj_lat, gcj_lng)

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Cookie": cookie,
        "Referer": "https://mobilelearn.chaoxing.com/",
    }

    try:
        resp = http_requests.get(sign_url, params=params, headers=headers, timeout=10)
        result_text = resp.text.strip()
        http_code = resp.status_code
        if http_code != 200:
            print(f"[do_sign] HTTP {http_code}: {result_text[:200]}")

        # 检测到滑块验证 → 不做求解，直接返回提示
        if "validate" in result_text.lower() and "success" not in result_text.lower():
            print(f"[do_sign] 检测到滑块验证，不再自动求解")
            result_text = "captcha_required"

        # ─── errorLocation1 降级策略 ───
        # 可能性1: location JSON 参数格式不被接受 → 改为直接传 top-level lat/lng
        # 可能性2: 没有 GPS 但老师开了定位 → 用默认值 -1
        if "errorLocation1" in result_text:
            print(f"[do_sign] errorLocation1，尝试降级方案1（top-level lat/lng）...")
            # 方案1: 去掉 location JSON，直接传 lat/lng 到顶层
            params.pop("location", None)
            params["latitude"] = gcj_lat if gcj_lat != "-1" else "39.9042"
            params["longitude"] = gcj_lng if gcj_lng != "-1" else "116.4074"
            resp2 = http_requests.get(sign_url, params=params, headers=headers, timeout=10)
            result_text = resp2.text.strip()
            http_code = resp2.status_code
            print(f"[do_sign] 降级方案1结果: {result_text[:80]}")

        if "errorLocation1" in result_text:
            # 方案2: 去掉所有定位相关参数，只保留核心
            print(f"[do_sign] errorLocation1 仍存在，尝试方案2（name+uid+ifTiJiao 二次请求）...")
            fallback_params = {
                "name": pk_name, "address": course_addr, "activeId": active_id,
                "uid": pk_uid, "clientip": "", "latitude": gcj_lat if gcj_lat != "-1" else "39.9042",
                "longitude": gcj_lng if gcj_lng != "-1" else "116.4074",
                "fid": pk_fid, "appType": "15", "ifTiJiao": "1",
            }
            resp2 = http_requests.get(sign_url, params=fallback_params, headers=headers, timeout=10)
            result_text = resp2.text.strip()
            http_code = resp2.status_code
            print(f"[do_sign] 降级方案2结果: {result_text[:80]}")

        # 判断签到结果
        if "success" in result_text.lower():
            status = "success"
            message = "签到成功"
        elif "已签到" in result_text or "签到过了" in result_text or "already" in result_text.lower():
            status = "success"
            message = "已签到"
        elif result_text == "captcha_required":
            status = "fail"
            message = "该课程有防作弊验证，请在学习通APP完成签到"
            # 自动标记课程
            course = Course.query.filter_by(id=course_id).first()
            if course and not course.has_captcha:
                course.has_captcha = True
                db.session.commit()
        elif "errorLocation1" in result_text:
            status = "fail"
            message = f"定位失败(errorLocation1): {result_text[:50]}"
        elif "请登录" in result_text or "login" in result_text.lower():
            status = "fail"
            message = "Cookie已失效"
        elif not result_text:
            status = "fail"
            message = f"签到接口返回空(HTTP {http_code})"
        else:
            status = "fail"
            message = f"签到失败: {result_text[:100]}"

        # 记录签到日志
        course = Course.query.filter_by(id=course_id).first()
        log = SignLog(
            user_id=uid,
            course_id=course_id,
            active_id=active_id,
            enc=enc,
            status=status,
            message=message,
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            "code": 200 if status == "success" else 502,
            "msg": message,
            "data": {
                "status": status,
                "raw_response": result_text[:200],
                "http_code": http_code,
                "cookie_length": len(cookie),
            }
        })

    except Exception as e:
        print(f"[do_sign] 异常: {e}")
        import traceback
        traceback.print_exc()
        log = SignLog(
            user_id=uid,
            course_id=course_id,
            active_id=active_id,
            enc=enc,
            status="fail",
            message=f"网络错误: {str(e)}",
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({"code": 502, "msg": f"请求异常: {str(e)}"}), 502


@consumer_bp.route("/sign-log", methods=["GET"])
def sign_log():
    """查询签到历史"""
    uid = request.args.get("uid")
    course_id = request.args.get("course_id")

    if not uid:
        return jsonify({"code": 400, "msg": "缺少uid"}), 400

    query = SignLog.query.filter_by(user_id=uid)
    if course_id:
        query = query.filter_by(course_id=course_id)

    logs = query.order_by(SignLog.created_at.desc()).limit(50).all()
    result = []
    for log in logs:
        course = Course.query.get(log.course_id)
        result.append({
            "id": log.id,
            "course_name": course.course_name if course else "未知课程",
            "active_id": log.active_id,
            "status": log.status,
            "message": log.message,
            "signed_at": log.created_at.strftime("%m-%d %H:%M:%S") if log.created_at else "",
        })

    return jsonify({"code": 200, "data": result})


@consumer_bp.route("/pending-courses", methods=["GET"])
def pending_courses():
    """
    查询用户加入的所有课程中，哪些课程当前有活跃MQ
    消费者守护进程用这个接口判断需要监控哪些课程
    """
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"code": 400, "msg": "缺少uid"}), 400

    memberships = CourseMember.query.filter_by(user_id=uid).all()
    active_courses = []
    for m in memberships:
        if mq_manager.course_has_active_mq(m.course_id):
            course = Course.query.get(m.course_id)
            if course:
                latest = mq_manager.get_latest_enc(m.course_id)
                active_courses.append({
                    "id": course.id,
                    "course_id": course.course_id,
                    "course_name": course.course_name,
                    "latest_enc": latest["enc"] if latest else None,
                    "active_id": latest["active_id"] if latest else None,
                    "mq_remaining_seconds": mq_manager.get_mq_ttl(m.course_id),
                })

    return jsonify({"code": 200, "data": active_courses})

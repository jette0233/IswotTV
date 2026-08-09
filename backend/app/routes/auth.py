import re
import json
import hashlib
import time
from datetime import datetime, timedelta
import requests as http_requests
import jwt as pyjwt
from flask import Blueprint, request, jsonify, current_app
from app.models.models import db, User

auth_bp = Blueprint("auth", __name__)


def make_token(user_id):
    payload = {
        "uid": user_id,
        "exp": int(time.time()) + 86400 * 7,  # 7天
    }
    return pyjwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")
    nickname = data.get("nickname", phone)

    if not phone or not password:
        return jsonify({"code": 400, "msg": "手机号和密码不能为空"}), 400

    if User.query.filter_by(phone=phone).first():
        return jsonify({"code": 409, "msg": "该手机号已注册"}), 409

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    user = User(phone=phone, nickname=nickname, password_hash=password_hash)
    db.session.add(user)
    db.session.commit()

    token = make_token(user.id)
    return jsonify({"code": 200, "msg": "注册成功", "data": {"token": token, "uid": user.id}})


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    phone = data.get("phone", "").strip()
    password = data.get("password", "")

    password_hash = hashlib.sha256(password.encode()).hexdigest()
    user = User.query.filter_by(phone=phone, password_hash=password_hash).first()

    if not user:
        return jsonify({"code": 401, "msg": "手机号或密码错误"}), 401

    token = make_token(user.id)
    cookie_status = "valid"
    expire = user.cookie_expire_at
    if expire and expire.tzinfo:
        expire = expire.replace(tzinfo=None)
    if expire and expire < datetime.utcnow():
        cookie_status = "expired"

    return jsonify({
        "code": 200,
        "msg": "登录成功",
        "data": {
            "token": token,
            "uid": user.id,
            "nickname": user.nickname,
            "is_admin": user.is_admin,
            "cookie_source": user.cookie_source,
            "cookie_status": cookie_status,
        }
    })


@auth_bp.route("/cookie/upload", methods=["POST"])
def upload_cookie():
    """方案2：用户手动抓取Cookie后上传"""
    data = request.get_json()
    uid = data.get("uid")
    cookie_str = data.get("cookie", "").strip()

    if not uid or not cookie_str:
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    # 从Cookie中提取_uid验证归属
    match = re.search(r'_uid=(\d+)', cookie_str)
    if not match:
        return jsonify({"code": 400, "msg": "Cookie格式无效，缺少_uid字段"}), 400

    cookie_uid = match.group(1)
    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    user.cookie_manual = cookie_str
    user.cookie_source = "manual"
    user.cookie_expire_at = datetime.utcnow() + timedelta(days=7)
    db.session.commit()

    return jsonify({"code": 200, "msg": "Cookie保存成功", "data": {"expire_at": user.cookie_expire_at.isoformat()}})


@auth_bp.route("/cookie/status", methods=["GET"])
def cookie_status():
    uid = request.args.get("uid")
    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    if not user.cookie_expire_at:
        return jsonify({"code": 200, "data": {"has_cookie": False}})

    now = datetime.utcnow()
    expire = user.cookie_expire_at
    if expire.tzinfo:
        expire = expire.replace(tzinfo=None)
    remaining = (expire - now).total_seconds()

    return jsonify({
        "code": 200,
        "data": {
            "has_cookie": True,
            "source": user.cookie_source,
            "expire_at": user.cookie_expire_at.isoformat(),
            "remaining_days": round(remaining / 86400, 1) if remaining > 0 else 0,
            "is_expired": remaining <= 0,
        }
    })


@auth_bp.route("/cookie/refresh-auto", methods=["POST"])
def refresh_cookie_auto():
    """方案1：用保存的密码自动刷新Cookie"""
    data = request.get_json()
    uid = data.get("uid")

    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    # 用前端传的学习通手机号和密码登录
    phone = data.get("phone", "").strip()
    password = data.get("password", "")

    if not phone or not password:
        return jsonify({"code": 400, "msg": "请提供学习通账号和密码"}), 400

    try:
        resp = http_requests.post(
            current_app.config["CHAOXING_LOGIN_URL"],
            data={"uname": phone, "password": password},
            timeout=15,
        )
        # 从响应中提取Cookie
        new_cookie = "; ".join([f"{k}={v}" for k, v in resp.cookies.items()])
        if not new_cookie:
            return jsonify({"code": 502, "msg": "学习通登录失败，可能账号密码错误"}), 502

        user.cookie_manual = new_cookie
        user.cookie_source = "auto"
        user.cookie_expire_at = datetime.utcnow() + timedelta(days=7)
        db.session.commit()

        return jsonify({"code": 200, "msg": "Cookie绑定成功", "data": {"expire_at": user.cookie_expire_at.isoformat()}})

    except Exception as e:
        return jsonify({"code": 502, "msg": f"登录请求失败: {str(e)}"}), 502


@auth_bp.route("/user/info", methods=["GET"])
def user_info():
    """用户信息（含 is_admin 状态）"""
    uid = request.args.get("uid")
    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404
    return jsonify({
        "code": 200,
        "data": {
            "id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "is_admin": user.is_admin,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    })

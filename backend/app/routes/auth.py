import re
import json
import time
from datetime import datetime, timedelta
import requests as http_requests
import jwt as pyjwt
from flask import Blueprint, request, jsonify, current_app
from app.models.models import db, User
from app.services.security import CredentialCipher, hash_password, make_access_token, require_user, verify_password
from flask import g

auth_bp = Blueprint("auth", __name__)


def make_token(user_id):
    user = User.query.get(user_id)
    return make_access_token(user, expires_seconds=86400 * 7)


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

    if len(password) < 8:
        return jsonify({"code": 400, "msg": "密码至少8位"}), 400
    password_hash = hash_password(password)
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

    user = User.query.filter_by(phone=phone).first()
    valid, needs_upgrade = verify_password(password, user.password_hash if user else None)

    if not user or not valid:
        return jsonify({"code": 401, "msg": "手机号或密码错误"}), 401
    if needs_upgrade:
        user.password_hash = hash_password(password)
        db.session.commit()

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
@require_user
def upload_cookie():
    """方案2：用户手动抓取Cookie后上传"""
    data = request.get_json()
    uid = g.current_user.id
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

    if user.cookie_manual:
        existing = re.search(r'_uid=(\d+)', CredentialCipher.decrypt(user.cookie_manual) or "")
        if existing and existing.group(1) != cookie_uid:
            return jsonify({"code": 400, "msg": "Cookie与已绑定学习通账号不一致"}), 400
    user.cookie_manual = CredentialCipher.encrypt(cookie_str)
    user.cookie_source = "manual"
    user.cookie_expire_at = datetime.utcnow() + timedelta(days=7)
    db.session.commit()

    return jsonify({"code": 200, "msg": "Cookie保存成功", "data": {"expire_at": user.cookie_expire_at.isoformat()}})


@auth_bp.route("/cookie/status", methods=["GET"])
@require_user
def cookie_status():
    uid = g.current_user.id
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
@require_user
def refresh_cookie_auto():
    """方案1：用保存的密码自动刷新Cookie"""
    data = request.get_json()
    uid = g.current_user.id

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
        new_uid = re.search(r'(?:^|;\s*)_uid=(\d+)', new_cookie)
        if not new_uid:
            return jsonify({"code": 502, "msg": "学习通登录失败，可能账号密码错误"}), 502

        old_cookie = CredentialCipher.decrypt(user.cookie_manual)
        old_uid = re.search(r'(?:^|;\s*)_uid=(\d+)', old_cookie or "")
        if old_uid and old_uid.group(1) != new_uid.group(1):
            return jsonify({"code": 400, "msg": "凭据与已绑定学习通账号不一致"}), 400

        user.cookie_manual = CredentialCipher.encrypt(new_cookie)
        user.cookie_source = "auto"
        user.cookie_expire_at = datetime.utcnow() + timedelta(days=7)
        db.session.commit()

        return jsonify({"code": 200, "msg": "Cookie绑定成功", "data": {"expire_at": user.cookie_expire_at.isoformat()}})

    except Exception as e:
        return jsonify({"code": 502, "msg": f"登录请求失败: {str(e)}"}), 502


@auth_bp.route("/user/info", methods=["GET"])
@require_user
def user_info():
    """用户信息（含 is_admin 状态）"""
    uid = g.current_user.id
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

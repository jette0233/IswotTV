"""
管理后台 — 入口隐藏于 /txjadmin，不对外暴露
使用独立账号密码登录（配置于 .env 的 ADMIN_USERNAME / ADMIN_PASSWORD）
"""
import time
import re
import jwt as pyjwt
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from app.models.models import db, User, Course, CourseMember, SignLog

admin_bp = Blueprint("admin", __name__, url_prefix="/api/txjadmin")


# ─── 辅助函数 ───

def _make_admin_token():
    """生成管理员 JWT"""
    payload = {
        "role": "admin",
        "exp": int(time.time()) + 86400,  # 24小时
    }
    return pyjwt.encode(payload, current_app.config["SECRET_KEY"], algorithm="HS256")


def _verify_admin_token(token):
    """验证管理员 JWT，成功返回 True，失败返回 False"""
    try:
        payload = pyjwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload.get("role") == "admin"
    except Exception:
        return False


def _get_token():
    """从 Authorization header 中提取 token。"""
    auth = request.headers.get("Authorization", "")
    m = re.match(r"Bearer\s+(.+)", auth)
    return m.group(1) if m else ""


def require_admin(f):
    """装饰器：需要有效的管理员 JWT"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = _get_token()
        if not token or not _verify_admin_token(token):
            return jsonify({"code": 401, "msg": "未登录或Token已过期，请重新登录管理后台"}), 401
        return f(*args, **kwargs)
    return wrapper


# ─── 管理员登录（独立账密，不依赖 User 表） ───

@admin_bp.route("/login", methods=["POST"])
def admin_login():
    """使用 .env 中配置的超级账号密码登录"""
    data = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"code": 400, "msg": "请输入账号和密码"}), 400

    from app.services.mq_manager import mq_manager
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()
    attempt_key = f"admin:login-attempts:{client_ip}"
    if mq_manager.redis:
        try:
            if int(mq_manager.redis.get(attempt_key) or 0) >= 5:
                return jsonify({"code": 429, "msg": "登录失败次数过多，请15分钟后重试"}), 429
        except Exception:
            pass

    # 验证账密
    expected_user = current_app.config["ADMIN_USERNAME"]
    expected_pwd = current_app.config["ADMIN_PASSWORD"]
    if username != expected_user or password != expected_pwd:
        if mq_manager.redis:
            try:
                attempts = mq_manager.redis.incr(attempt_key)
                if attempts == 1:
                    mq_manager.redis.expire(attempt_key, 900)
            except Exception:
                pass
        return jsonify({"code": 401, "msg": "管理员账号或密码错误"}), 401

    if mq_manager.redis:
        try:
            mq_manager.redis.delete(attempt_key)
        except Exception:
            pass

    token = _make_admin_token()
    return jsonify({
        "code": 200,
        "msg": "管理员登录成功",
        "data": {"token": token, "expires_in": 86400},
    })





# ─── 仪表盘 ───

@admin_bp.route("/dashboard", methods=["GET"])
@require_admin
def dashboard():
    total_users = User.query.count()
    total_courses = Course.query.count()
    total_logs = SignLog.query.count()
    active_captcha_courses = Course.query.filter_by(has_captcha=True).count()
    today_logs = SignLog.query.filter(
        SignLog.created_at >= db.func.current_date()
    ).count()

    return jsonify({
        "code": 200,
        "data": {
            "total_users": total_users,
            "total_courses": total_courses,
            "total_sign_logs": total_logs,
            "active_captcha_courses": active_captcha_courses,
            "today_sign_logs": today_logs,
        }
    })


# ─── 用户列表 ───

@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    keyword = request.args.get("keyword", "")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    query = User.query
    if keyword:
        query = query.filter(
            db.or_(User.nickname.contains(keyword), User.phone.contains(keyword))
        )

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "code": 200,
        "data": {
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "users": [{
                "id": u.id,
                "nickname": u.nickname,
                "phone": u.phone,
                "has_cookie": bool(u.cookie_manual),
                "cookie_source": u.cookie_source,
                "cookie_expire_at": u.cookie_expire_at.isoformat() if u.cookie_expire_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            } for u in pagination.items]
        }
    })


# ─── 课程列表（全部课程，含过滤） ───

@admin_bp.route("/courses", methods=["GET"])
@require_admin
def list_courses():
    keyword = request.args.get("keyword", "")
    captcha_filter = request.args.get("has_captcha", "")  # "1"/"0"/""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    query = Course.query
    if keyword:
        query = query.filter(Course.course_name.contains(keyword))
    if captcha_filter in ("1", "0"):
        query = query.filter_by(has_captcha=bool(int(captcha_filter)))

    pagination = query.order_by(Course.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    from app.services.mq_manager import mq_manager
    return jsonify({
        "code": 200,
        "data": {
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "courses": [{
                "id": c.id,
                "course_id": c.course_id,
                "course_name": c.course_name,
                "teacher_name": c.teacher_name or "",
                "has_captcha": c.has_captcha,
                "is_active": c.is_active,
                "creator_id": c.creator_id,
                "creator_nickname": User.query.get(c.creator_id).nickname if User.query.get(c.creator_id) else str(c.creator_id),
                "member_count": CourseMember.query.filter_by(course_id=c.id).count(),
                "has_active_mq": mq_manager.course_has_active_mq(c.id),
                "created_at": c.created_at.isoformat() if c.created_at else None,
            } for c in pagination.items]
        }
    })


# ─── 课程详情（admin 用，含全部字段 + 成员列表） ───

@admin_bp.route("/course/detail", methods=["GET"])
@require_admin
def admin_course_detail():
    course_id = request.args.get("course_id")
    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    creator = User.query.get(course.creator_id)
    members = CourseMember.query.filter_by(course_id=course.id).all()
    member_list = []
    for m in members:
        u = User.query.get(m.user_id)
        if u:
            member_list.append({
                "uid": u.id,
                "nickname": u.nickname,
                "phone": u.phone,
                "is_creator": u.id == course.creator_id,
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            })

    return jsonify({
        "code": 200,
        "data": {
            "id": course.id,
            "course_id": course.course_id,
            "course_name": course.course_name,
            "teacher_name": course.teacher_name or "",
            "address": course.address or "",
            "weekdays": course.weekdays,
            "default_latitude": course.default_latitude or "",
            "default_longitude": course.default_longitude or "",
            "has_captcha": course.has_captcha,
            "is_active": course.is_active,
            "creator_id": course.creator_id,
            "creator_nickname": creator.nickname if creator else str(course.creator_id),
            "member_count": len(member_list),
            "members": member_list,
        }
    })


# ─── 管理后台强制开关 has_captcha ───

@admin_bp.route("/course/toggle-captcha", methods=["POST"])
@require_admin
def toggle_captcha():
    data = request.get_json()
    course_id = data.get("course_id")
    has_captcha = data.get("has_captcha", False)

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    course.has_captcha = bool(has_captcha)
    db.session.commit()
    return jsonify({"code": 200, "msg": "已更新", "data": {"has_captcha": course.has_captcha}})


# ─── 课程编辑（全字段） ───

@admin_bp.route("/course/create", methods=["POST"])
@require_admin
def admin_create_course():
    data = request.get_json() or {}
    external_id = str(data.get("course_id", "")).strip()
    if not external_id:
        return jsonify({"code": 400, "msg": "缺少course_id"}), 400
    if Course.query.filter_by(course_id=external_id).first():
        return jsonify({"code": 409, "msg": "课程已存在"}), 409
    admin_user = User.query.filter_by(is_admin=True).order_by(User.id.asc()).first()
    if not admin_user:
        return jsonify({"code": 409, "msg": "请先创建并绑定前台admin代理账户"}), 409
    course = Course(
        course_id=external_id, course_name=data.get("course_name") or external_id,
        teacher_name=data.get("teacher_name"), address=data.get("address"), weekdays=data.get("weekdays") or "1,2,3,4,5",
        default_latitude=data.get("default_latitude"), default_longitude=data.get("default_longitude"),
        creator_id=admin_user.id, is_active=True, has_captcha=bool(data.get("has_captcha", False)),
    )
    db.session.add(course)
    db.session.flush()
    db.session.add(CourseMember(user_id=admin_user.id, course_id=course.id))
    db.session.commit()
    return jsonify({"code": 200, "msg": "课程创建成功", "data": {"id": course.id}})

@admin_bp.route("/course/update", methods=["POST"])
@require_admin
def admin_update_course():
    data = request.get_json()
    course_id = data.get("course_id")
    if not course_id:
        return jsonify({"code": 400, "msg": "缺少course_id"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    if "course_name" in data: course.course_name = data["course_name"]
    if "teacher_name" in data: course.teacher_name = data["teacher_name"]
    if "address" in data: course.address = data.get("address") or None
    if "weekdays" in data: course.weekdays = data["weekdays"]
    if "default_latitude" in data: course.default_latitude = data.get("default_latitude") or None
    if "default_longitude" in data: course.default_longitude = data.get("default_longitude") or None
    if "has_captcha" in data: course.has_captcha = data["has_captcha"]
    if "is_active" in data: course.is_active = data["is_active"]
    db.session.commit()

    return jsonify({"code": 200, "msg": "课程已更新", "data": {"id": course.id, "course_name": course.course_name, "has_captcha": course.has_captcha}})


# ─── 课程删除 ───

@admin_bp.route("/course/delete", methods=["POST"])
@require_admin
def admin_delete_course():
    data = request.get_json()
    course_id = data.get("course_id")
    if not course_id:
        return jsonify({"code": 400, "msg": "缺少course_id"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    CourseMember.query.filter_by(course_id=course.id).delete()
    SignLog.query.filter_by(course_id=course.id).delete()
    db.session.delete(course)
    db.session.commit()
    return jsonify({"code": 200, "msg": "课程已删除"})


# ─── 踢出课程成员（admin 专用） ───

@admin_bp.route("/course/kick-member", methods=["POST"])
@require_admin
def admin_kick_member():
    data = request.get_json()
    course_id = data.get("course_id")
    uid = data.get("uid")

    if not course_id or not uid:
        return jsonify({"code": 400, "msg": "缺少course_id或uid"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    if int(uid) == course.creator_id:
        return jsonify({"code": 400, "msg": "不能踢出课程创建者"}), 400

    member = CourseMember.query.filter_by(user_id=uid, course_id=course.id).first()
    if not member:
        return jsonify({"code": 404, "msg": "该用户不是课程成员"}), 404

    db.session.delete(member)
    db.session.commit()
    return jsonify({"code": 200, "msg": "已踢出成员"})


# ─── 修改课程创建者（admin 专用） ───

@admin_bp.route("/course/change-creator", methods=["POST"])
@require_admin
def admin_change_creator():
    data = request.get_json()
    course_id = data.get("course_id")

    if not course_id:
        return jsonify({"code": 400, "msg": "缺少course_id"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    admin_user = User.query.filter_by(is_admin=True).order_by(User.id.asc()).first()
    if not admin_user:
        admin_user = User.query.filter_by(phone=current_app.config["ADMIN_USERNAME"]).first()
    if not admin_user:
        admin_user = User.query.filter_by(nickname=current_app.config["ADMIN_USERNAME"]).first()
    if not admin_user:
        admin_user = User(
            nickname=current_app.config["ADMIN_USERNAME"],
            phone=current_app.config["ADMIN_USERNAME"],
            password_hash=None,
            is_admin=True,
        )
        db.session.add(admin_user)
        db.session.flush()
    else:
        if not admin_user.is_admin:
            admin_user.is_admin = True

    member = CourseMember.query.filter_by(user_id=admin_user.id, course_id=course.id).first()
    if not member:
        db.session.add(CourseMember(user_id=admin_user.id, course_id=course.id))

    course.creator_id = admin_user.id
    db.session.commit()
    return jsonify({"code": 200, "msg": "课程已转交给超级管理员", "data": {"creator_id": admin_user.id, "creator_nickname": admin_user.nickname}})


# ─── 用户删除 ───

@admin_bp.route("/user/delete", methods=["POST"])
@require_admin
def admin_delete_user():
    data = request.get_json()
    uid = data.get("uid")
    if not uid:
        return jsonify({"code": 400, "msg": "缺少uid"}), 400

    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    owned_courses = Course.query.filter_by(creator_id=user.id).count()
    if owned_courses:
        return jsonify({"code": 409, "msg": f"该用户仍拥有{owned_courses}门课程，请先转让或删除课程"}), 409

    CourseMember.query.filter_by(user_id=user.id).delete()
    SignLog.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    return jsonify({"code": 200, "msg": "用户已删除"})


# ─── 签到日志查询 ───

@admin_bp.route("/sign-logs", methods=["GET"])
@require_admin
def sign_logs():
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))

    pagination = SignLog.query.order_by(SignLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    return jsonify({
        "code": 200,
        "data": {
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "logs": [{
                "id": l.id,
                "user_id": l.user_id,
                "course_id": l.course_id,
                "status": l.status,
                "message": l.message,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            } for l in pagination.items]
        }
    })

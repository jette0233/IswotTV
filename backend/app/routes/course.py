from flask import Blueprint, request, jsonify, g
from app.models.models import db, Course, CourseMember, User
from app.services.security import require_user

course_bp = Blueprint("course", __name__)


def _can_read_course(uid, course):
    """用户是否有权查看课程：创建者/成员/admin"""
    if not uid:
        return False
    user = User.query.get(uid)
    if user and user.is_admin:
        return True
    if course.creator_id == int(uid):
        return True
    member = CourseMember.query.filter_by(user_id=uid, course_id=course.id).first()
    return member is not None


def _can_write_course(uid, course):
    """用户是否有权修改/删除课程：创建者/admin"""
    if not uid:
        return False
    user = User.query.get(uid)
    if user and user.is_admin:
        return True
    return course.creator_id == int(uid)


# ─── create: 任何用户都可以创建 ───

@course_bp.route("/create", methods=["POST"])
@require_user
def create_course():
    data = request.get_json()
    creator_id = g.current_user.id
    course_id = data.get("course_id", "").strip()
    course_name = data.get("course_name", course_id)
    address = data.get("address", "").strip()
    weekdays = data.get("weekdays", "1,2,3,4,5")
    dlat = data.get("default_latitude", "").strip()
    dlng = data.get("default_longitude", "").strip()

    if not creator_id or not course_id:
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    if not User.query.get(creator_id):
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    existing = Course.query.filter_by(course_id=course_id).first()
    if existing:
        return jsonify({"code": 409, "msg": "该课程已存在", "data": {"course_id": existing.id}}), 409

    has_captcha = data.get("has_captcha", False)
    course = Course(course_id=course_id, course_name=course_name, address=address,
                    default_latitude=dlat or None, default_longitude=dlng or None,
                    weekdays=weekdays, creator_id=creator_id, teacher_name=data.get("teacher_name"),
                    has_captcha=has_captcha)
    db.session.add(course)
    db.session.flush()

    member = CourseMember(user_id=creator_id, course_id=course.id)
    db.session.add(member)
    db.session.commit()

    return jsonify({
        "code": 200, "msg": "课程创建成功",
        "data": {"id": course.id, "course_id": course.course_id, "course_name": course.course_name, "address": course.address, "weekdays": course.weekdays, "has_captcha": course.has_captcha}
    })


# ─── join: 任何已登录用户都可以加入 ───

@course_bp.route("/join", methods=["POST"])
@require_user
def join_course():
    """加入一个课程"""
    data = request.get_json()
    user_id = g.current_user.id
    course_id = data.get("course_id")  # 可以是mysql id或学习通courseId

    if not user_id or not course_id:
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    course = Course.query.filter_by(id=course_id).first()
    if not course:
        course = Course.query.filter_by(course_id=str(course_id)).first()
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    existing = CourseMember.query.filter_by(user_id=user_id, course_id=course.id).first()
    if existing:
        return jsonify({"code": 409, "msg": "已加入该课程"}), 409

    member = CourseMember(user_id=user_id, course_id=course.id)
    db.session.add(member)
    db.session.commit()

    return jsonify({"code": 200, "msg": "加入成功", "data": {"course_id": course.id, "course_name": course.course_name}})


# ─── leave: 退出课程 ───

@course_bp.route("/leave", methods=["POST"])
@require_user
def leave_course():
    """退出课程（删除自己的成员记录）"""
    data = request.get_json()
    user_id = g.current_user.id
    course_id = data.get("course_id")

    if not user_id or not course_id:
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    member = CourseMember.query.filter_by(user_id=user_id, course_id=course_id).first()
    if not member:
        return jsonify({"code": 404, "msg": "你未加入该课程"}), 404

    course = Course.query.get(course_id)
    if course and course.creator_id == user_id:
        return jsonify({"code": 400, "msg": "课程创建者不能直接退出，请先转让或删除课程"}), 400

    db.session.delete(member)
    db.session.commit()
    return jsonify({"code": 200, "msg": "已退出课程"})


# ─── list: 创建者/成员/admin 可见 ───

@course_bp.route("/list", methods=["GET"])
@require_user
def list_courses():
    uid = g.current_user.id
    weekday = request.args.get("weekday")
    if not uid:
        return jsonify({"code": 400, "msg": "缺少uid"}), 400

    user = User.query.get(uid)
    if not user:
        return jsonify({"code": 404, "msg": "用户不存在"}), 404

    # admin：看到所有课程
    if user.is_admin:
        courses = Course.query.filter_by(is_active=True).all()
        result = []
        for course in courses:
            if weekday:
                days = [d.strip() for d in course.weekdays.split(",")]
                if weekday not in days:
                    continue
            from app.services.mq_manager import mq_manager
            has_active_mq = mq_manager.course_has_active_mq(course.id)
            result.append({
                "id": course.id,
                "course_id": course.course_id,
                "course_name": course.course_name,
                "address": course.address or "",
                "weekdays": course.weekdays,
                "has_captcha": course.has_captcha,
                "has_active_mq": has_active_mq,
                "is_creator": course.creator_id == int(uid),
            })
        return jsonify({"code": 200, "data": result})

    # 普通用户：只看到自己创建或加入的课程
    memberships = CourseMember.query.filter_by(user_id=uid).all()
    result = []
    for m in memberships:
        course = Course.query.get(m.course_id)
        if course and course.is_active:
            if weekday:
                days = [d.strip() for d in course.weekdays.split(",")]
                if weekday not in days:
                    continue
            from app.services.mq_manager import mq_manager
            has_active_mq = mq_manager.course_has_active_mq(course.id)
            result.append({
                "id": course.id,
                "course_id": course.course_id,
                "course_name": course.course_name,
                "teacher_name": course.teacher_name or "",
                "address": course.address or "",
                "weekdays": course.weekdays,
                "has_captcha": course.has_captcha,
                "has_active_mq": has_active_mq,
                "is_creator": course.creator_id == int(uid),
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            })

    return jsonify({"code": 200, "data": result})


# ─── detail: 创建者/成员/admin 可见 ───

@course_bp.route("/detail", methods=["GET"])
@require_user
def course_detail():
    """课程详情（含成员列表）"""
    course_id = request.args.get("course_id")
    uid = g.current_user.id

    if not uid:
        return jsonify({"code": 400, "msg": "缺少uid"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    if not _can_read_course(uid, course):
        return jsonify({"code": 403, "msg": "无权查看该课程"}), 403

    members = CourseMember.query.filter_by(course_id=course.id).all()
    member_list = []
    for m in members:
        user = User.query.get(m.user_id)
        if user:
            member_list.append({"uid": user.id, "nickname": user.nickname})

    return jsonify({
        "code": 200,
        "data": {
            "id": course.id,
            "course_id": course.course_id,
            "course_name": course.course_name,
            "address": course.address or "",
            "weekdays": course.weekdays,
            "has_captcha": course.has_captcha,
            "creator_id": course.creator_id,
            "is_creator": course.creator_id == int(uid),
            "member_count": len(member_list),
            "members": member_list,
        }
    })


# ─── update: 仅创建者/admin ───

@course_bp.route("/update", methods=["POST"])
@require_user
def update_course():
    """修改课程信息"""
    data = request.get_json()
    course_id = data.get("course_id")
    uid = g.current_user.id

    if not course_id or not uid:
        return jsonify({"code": 400, "msg": "缺少course_id或uid"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    if not _can_write_course(uid, course):
        return jsonify({"code": 403, "msg": "无权修改该课程"}), 403

    if data.get("course_name"): course.course_name = data["course_name"]
    if "teacher_name" in data: course.teacher_name = data["teacher_name"]
    if "address" in data: course.address = data.get("address") or None
    if "weekdays" in data: course.weekdays = data["weekdays"]
    if "default_latitude" in data: course.default_latitude = data.get("default_latitude") or None
    if "default_longitude" in data: course.default_longitude = data.get("default_longitude") or None
    if "has_captcha" in data: course.has_captcha = data["has_captcha"]
    db.session.commit()

    return jsonify({"code": 200, "msg": "课程信息已更新", "data": {"has_captcha": course.has_captcha}})


# ─── delete: 仅创建者/admin ───

@course_bp.route("/delete", methods=["POST"])
@require_user
def delete_course():
    """删除课程"""
    data = request.get_json()
    course_id = data.get("course_id")
    uid = g.current_user.id

    if not course_id or not uid:
        return jsonify({"code": 400, "msg": "缺少course_id或uid"}), 400

    course = Course.query.get(course_id)
    if not course:
        return jsonify({"code": 404, "msg": "课程不存在"}), 404

    if not _can_write_course(uid, course):
        return jsonify({"code": 403, "msg": "无权删除该课程"}), 403

    from app.models.models import SignLog
    SignLog.query.filter_by(course_id=course.id).delete()
    CourseMember.query.filter_by(course_id=course.id).delete()
    db.session.delete(course)
    db.session.commit()
    return jsonify({"code": 200, "msg": "课程已删除"})

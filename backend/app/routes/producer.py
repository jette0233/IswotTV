from flask import Blueprint, request, jsonify, g
from app.models.models import db, Course, CourseMember
from app.services.mq_manager import mq_manager
from app.services.security import require_user

producer_bp = Blueprint("producer", __name__)


@producer_bp.route("/claim", methods=["POST"])
@require_user
def claim_producer():
    """生产者竞选"""
    data = request.get_json()
    course_id = data.get("course_id")
    user_id = g.current_user.id

    if not course_id or not user_id:
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    # 验证用户是该课程成员
    member = CourseMember.query.filter_by(user_id=user_id, course_id=course_id).first()
    if not member:
        return jsonify({"code": 403, "msg": "你不是该课程成员"}), 403

    # 检查课程是否有滑动验证码
    course = Course.query.get(course_id)
    if course and course.has_captcha:
        return jsonify({"code": 403, "msg": "该课程有防作弊验证，请在手机端学习通APP完成签到", "data": {"blocked_by_captcha": True}}), 403

    success, msg = mq_manager.claim_producer(course_id, user_id)
    if success:
        return jsonify({"code": 200, "msg": msg, "data": {"is_producer": True}})
    else:
        current_uid = mq_manager.get_current_producer(course_id)
        return jsonify({"code": 200, "msg": msg, "data": {"is_producer": False, "current_producer_uid": current_uid}})


@producer_bp.route("/heartbeat", methods=["POST"])
@require_user
def producer_heartbeat():
    """生产者心跳"""
    data = request.get_json()
    course_id = data.get("course_id")
    user_id = g.current_user.id

    if not CourseMember.query.filter_by(user_id=user_id, course_id=course_id).first():
        return jsonify({"code": 403, "msg": "你不是该课程成员"}), 403

    course = Course.query.get(course_id)
    if course and course.has_captcha:
        return jsonify({"code": 403, "msg": "该课程有防作弊验证，已暂停", "data": {"blocked_by_captcha": True}}), 403

    success, msg = mq_manager.heartbeat(course_id, user_id)
    return jsonify({"code": 200 if success else 400, "msg": msg})


@producer_bp.route("/push-enc", methods=["POST"])
@require_user
def push_enc():
    """推送enc到MQ"""
    data = request.get_json()
    course_id = data.get("course_id")
    user_id = g.current_user.id
    enc = data.get("enc", "").strip()
    active_id = data.get("active_id", "").strip()
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if not all([course_id, user_id, enc, active_id]):
        return jsonify({"code": 400, "msg": "参数不完整"}), 400

    if not CourseMember.query.filter_by(user_id=user_id, course_id=course_id).first():
        return jsonify({"code": 403, "msg": "你不是该课程成员"}), 403

    course = Course.query.get(course_id)
    if course and course.has_captcha:
        return jsonify({"code": 403, "msg": "该课程有防作弊验证，已暂停推送", "data": {"blocked_by_captcha": True}}), 403

    current_producer = mq_manager.get_current_producer(course_id)
    if str(current_producer) != str(user_id):
        return jsonify({"code": 403, "msg": "你不是当前生产者"}), 403

    success, is_new = mq_manager.push_enc(course_id, enc, active_id, latitude, longitude)
    return jsonify({
        "code": 200 if success else 500,
        "msg": "enc推送成功" if success else "推送失败",
        "data": {"is_new_mq": is_new}
    })


@producer_bp.route("/status", methods=["GET"])
@require_user
def producer_status():
    """查看生产者状态"""
    course_id = request.args.get("course_id")
    if not course_id:
        return jsonify({"code": 400, "msg": "缺少course_id"}), 400
    if not CourseMember.query.filter_by(user_id=g.current_user.id, course_id=course_id).first():
        return jsonify({"code": 403, "msg": "你不是该课程成员"}), 403

    uid = mq_manager.get_current_producer(course_id)
    has_mq = mq_manager.course_has_active_mq(course_id)
    ttl = mq_manager.get_mq_ttl(course_id) if has_mq else 0

    return jsonify({
        "code": 200,
        "data": {
            "current_producer_uid": uid,
            "has_active_mq": has_mq,
            "mq_remaining_seconds": ttl,
        }
    })

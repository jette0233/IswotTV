"""
课堂签到助手 - 后端 (API only)
"""
import os
import redis as redis_lib
from flask import Flask
from flask_cors import CORS
from config import Config
from app.models.models import db
from app.routes.auth import auth_bp
from app.routes.course import course_bp
from app.routes.producer import producer_bp
from app.routes.consumer import consumer_bp
from app.routes.admin import admin_bp
from app.services.mq_manager import mq_manager
from app.services.auto_signer import auto_signer


def create_app():
    Config.validate()
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    db.init_app(app)

    # 初始化Redis
    redis_client = redis_lib.Redis(
        host=app.config["REDIS_HOST"],
        port=app.config["REDIS_PORT"],
        db=app.config["REDIS_DB"],
        decode_responses=True,
    )
    mq_manager.redis = redis_client

    # 注册蓝图
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(course_bp, url_prefix="/api/course")
    app.register_blueprint(producer_bp, url_prefix="/api/producer")
    app.register_blueprint(consumer_bp, url_prefix="/api/consumer")
    app.register_blueprint(admin_bp)

    # 健康检查
    @app.route("/api/health")
    def health():
        redis_ok = False
        try:
            redis_ok = mq_manager.redis.ping() if mq_manager.redis else False
        except:
            pass
        return {
            "status": "ok" if redis_ok else "degraded",
            "redis": redis_ok,
            "auto_signer": auto_signer._enabled,
        }

    # Schema changes are managed by Alembic; the web process never mutates schema.
    with app.app_context():
        if mq_manager.redis:
            try:
                mq_manager.redis.ping()
                print("[OK] Redis 连接成功")
            except:
                print("[WARN] Redis 连接失败")
        else:
            print("[WARN] Redis 未配置")

        if app.config["START_EMBEDDED_SIGNER"]:
            auto_signer.start(app)
            print("[WARN] 已启动兼容模式内嵌Signer；生产环境应使用独立worker")

    return app


if __name__ == "__main__":
    app = create_app()
    print("=" * 50)
    print("课堂签到助手 已启动")
    print(f"  后端API: http://localhost:5000")
    print(f"  访问前端: https://10.110.247.25:5173")
    print(f"  开发地址: https://localhost:5173")
    print(f"  (Vite前端自带HTTPS，反代API到:5000)")
    print(f"  Redis: {Config.REDIS_HOST}:{Config.REDIS_PORT}")
    print(f"  MySQL: {Config.MYSQL_HOST}:{Config.MYSQL_PORT}/{Config.MYSQL_DB}")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=True)

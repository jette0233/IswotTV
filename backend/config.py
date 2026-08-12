import os
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()


class Config:
    ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")).lower()
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

    # MySQL
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "chaoxing_sign")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{quote_plus(MYSQL_USER)}:{quote_plus(MYSQL_PASSWORD)}"
        f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))

    # 业务配置
    MQ_TTL_SECONDS = int(os.getenv("MQ_TTL_SECONDS", 1200))  # 20min
    PRODUCER_HEARTBEAT_TIMEOUT = int(os.getenv("PRODUCER_HEARTBEAT_TIMEOUT", 15))  # 秒

    # 学习通签到API
    CHAOXING_SIGN_URL = "https://mobilelearn.chaoxing.com/pptSign/stuSignajax"
    CHAOXING_LOGIN_URL = "https://passport2.chaoxing.com/fanyalogin"

    # 管理后台独立账号
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
    CREDENTIAL_ENCRYPTION_KEY = os.getenv("CREDENTIAL_ENCRYPTION_KEY", "")
    CORS_ORIGINS = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if v.strip()]
    START_EMBEDDED_SIGNER = os.getenv("START_EMBEDDED_SIGNER", "false").lower() == "true"

    @classmethod
    def validate(cls):
        if cls.ENV in {"production", "prod"}:
            missing = []
            if cls.SECRET_KEY == "dev-secret-key" or len(cls.SECRET_KEY) < 32:
                missing.append("SECRET_KEY")
            if cls.ADMIN_PASSWORD == "admin123" or len(cls.ADMIN_PASSWORD) < 12:
                missing.append("ADMIN_PASSWORD")
            if not cls.CREDENTIAL_ENCRYPTION_KEY:
                missing.append("CREDENTIAL_ENCRYPTION_KEY")
            if not cls.MYSQL_PASSWORD:
                missing.append("MYSQL_PASSWORD")
            if missing:
                raise RuntimeError(f"Unsafe production configuration: {', '.join(missing)}")

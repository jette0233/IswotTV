from functools import lru_cache
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "dev-secret-key"
    credential_encryption_key: str = ""
    cors_origins: str = "http://localhost:5173"
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_db: str = "chaoxing"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    mq_ttl_seconds: int = 1200
    producer_heartbeat_timeout: int = 15
    worker_concurrency: int = 20
    worker_lease_seconds: int = 30
    chaoxing_sign_url: str = "https://mobilelearn.chaoxing.com/pptSign/stuSignajax"

    @property
    def async_database_url(self) -> str:
        return (
            f"mysql+asyncmy://{quote_plus(self.mysql_user)}:{quote_plus(self.mysql_password)}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    def validate_production(self) -> None:
        if self.app_env.lower() not in {"production", "prod"}:
            return
        missing = []
        if self.secret_key == "dev-secret-key" or len(self.secret_key) < 32:
            missing.append("SECRET_KEY")
        if not self.credential_encryption_key:
            missing.append("CREDENTIAL_ENCRYPTION_KEY")
        if not self.mysql_password:
            missing.append("MYSQL_PASSWORD")
        if missing:
            raise RuntimeError(f"Unsafe production configuration: {', '.join(missing)}")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_production()
    return settings

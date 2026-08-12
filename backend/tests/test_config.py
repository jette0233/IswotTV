import pytest

from v2.settings import Settings


def test_production_rejects_default_secrets():
    settings = Settings(app_env="production", secret_key="dev-secret-key", mysql_password="", credential_encryption_key="")
    with pytest.raises(RuntimeError):
        settings.validate_production()


def test_development_allows_local_defaults():
    Settings(app_env="development").validate_production()

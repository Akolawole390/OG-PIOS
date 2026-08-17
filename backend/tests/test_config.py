import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_construct_fine_with_default_secret_key_in_development():
    # The default placeholder is fine in development — this is what every local/test run uses.
    settings = Settings(environment="development", secret_key="changeme-generate-with-openssl-rand-hex-32")
    assert settings.secret_key == "changeme-generate-with-openssl-rand-hex-32"


def test_settings_refuse_default_secret_key_in_production():
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(environment="production", secret_key="changeme-generate-with-openssl-rand-hex-32")


def test_settings_construct_fine_with_real_secret_key_in_production():
    settings = Settings(environment="production", secret_key="a-real-randomly-generated-secret")
    assert settings.environment == "production"

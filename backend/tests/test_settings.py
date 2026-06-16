import pytest
from pydantic import ValidationError

from backend.src.core.settings import Settings

def test_development_environment_allows_default_key():
    """Development environment should allow the default 'change-me-in-production' key."""
    settings = Settings(environment="development")
    assert settings.environment == "development"
    assert settings.auth_secret_key == "change-me-in-production"

def test_production_environment_rejects_default_key():
    """Production environment must not allow the default 'change-me-in-production' key."""
    with pytest.raises(ValidationError, match="auth_secret_key must be overridden in production environment"):
        Settings(environment="production", auth_secret_key="change-me-in-production")

def test_production_environment_accepts_secure_key():
    """Production environment should allow a different key to be configured."""
    settings = Settings(environment="production", auth_secret_key="secure-super-secret-key-12345")
    assert settings.environment == "production"
    assert settings.auth_secret_key == "secure-super-secret-key-12345"

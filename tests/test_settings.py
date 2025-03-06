from collections.abc import Generator
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from supabase_mcp.settings import SUPPORTED_REGIONS, Settings


@pytest.fixture(autouse=True)
def reset_settings_singleton() -> Generator[None, None, None]:
    """Reset the Settings singleton before each test"""
    # Clear singleton instance if it exists
    if hasattr(Settings, "_instance"):
        delattr(Settings, "_instance")
    yield
    # Clean up after test
    if hasattr(Settings, "_instance"):
        delattr(Settings, "_instance")


@pytest.mark.integration
def test_settings_default_values(clean_environment: None) -> None:
    """Test default values (no config file, no env vars)"""
    settings = Settings.with_config()  # No config file
    assert settings.supabase_project_ref == "127.0.0.1:54322"
    assert settings.supabase_db_password == "postgres"
    assert settings.supabase_region == "us-east-1"
    assert settings.supabase_access_token is None
    assert settings.supabase_service_role_key is None


@pytest.mark.integration
def test_settings_from_env_test(clean_environment: None) -> None:
    """Test loading from .env.test"""
    settings = Settings.with_config(".env.test")
    # These values should match what's in your .env.test file
    assert settings.supabase_project_ref != "127.0.0.1:54322"  # Should be overridden by .env.test
    assert settings.supabase_db_password != "postgres"  # Should be overridden by .env.test
    # Check that the values are not empty
    assert settings.supabase_project_ref, "Project ref should not be empty"
    assert settings.supabase_db_password, "DB password should not be empty"


@pytest.mark.integration
def test_settings_from_env_vars(clean_environment: None) -> None:
    """Test env vars take precedence over config file"""
    env_values = {"SUPABASE_PROJECT_REF": "from-env", "SUPABASE_DB_PASSWORD": "env-password"}
    with patch.dict("os.environ", env_values, clear=False):
        settings = Settings.with_config(".env.test")  # Even with config file
        assert settings.supabase_project_ref == "from-env"
        assert settings.supabase_db_password == "env-password"


@pytest.mark.integration
def test_settings_integration_fixture(settings_integration: Settings) -> None:
    """Test the settings_integration fixture provides valid settings."""
    # The settings_integration fixture should load from .env.test or environment variables
    assert settings_integration.supabase_project_ref, "Project ref should not be empty"
    assert settings_integration.supabase_db_password, "DB password should not be empty"
    assert settings_integration.supabase_region, "Region should not be empty"


@pytest.mark.integration
def test_settings_region_validation() -> None:
    """Test region validation."""
    # Test default region
    settings = Settings()
    assert settings.supabase_region == "us-east-1"

    # Test valid region from environment
    env_values = {"SUPABASE_REGION": "ap-southeast-1"}
    with patch.dict("os.environ", env_values, clear=True):
        settings = Settings()
        assert settings.supabase_region == "ap-southeast-1"

    # Test invalid region
    with pytest.raises(ValidationError) as exc_info:
        env_values = {"SUPABASE_REGION": "invalid-region"}
        with patch.dict("os.environ", env_values, clear=True):
            Settings()
    assert "Region 'invalid-region' is not supported" in str(exc_info.value)


@pytest.mark.integration
def test_supported_regions() -> None:
    """Test that all supported regions are valid."""
    for region in SUPPORTED_REGIONS.__args__:
        env_values = {"SUPABASE_REGION": region}
        with patch.dict("os.environ", env_values, clear=True):
            settings = Settings()
            assert settings.supabase_region == region


@pytest.mark.integration
def test_settings_access_token_and_service_role() -> None:
    """Test access token and service role key settings."""
    # Test with environment variables
    env_values = {"SUPABASE_ACCESS_TOKEN": "test-access-token", "SUPABASE_SERVICE_ROLE_KEY": "test-service-role-key"}
    with patch.dict("os.environ", env_values, clear=True):
        settings = Settings()
        assert settings.supabase_access_token == "test-access-token"
        assert settings.supabase_service_role_key == "test-service-role-key"

    # Test defaults (should be None)
    with patch.dict("os.environ", {}, clear=True):
        settings = Settings()
        assert settings.supabase_access_token is None
        assert settings.supabase_service_role_key is None

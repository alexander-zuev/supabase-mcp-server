import os
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from supabase_mcp.logger import logger

SUPPORTED_REGIONS = Literal[
    "us-west-1",  # West US (North California)
    "us-east-1",  # East US (North Virginia)
    "us-east-2",  # East US (Ohio)
    "ca-central-1",  # Canada (Central)
    "eu-west-1",  # West EU (Ireland)
    "eu-west-2",  # West Europe (London)
    "eu-west-3",  # West EU (Paris)
    "eu-central-1",  # Central EU (Frankfurt)
    "eu-central-2",  # Central Europe (Zurich)
    "eu-north-1",  # North EU (Stockholm)
    "ap-south-1",  # South Asia (Mumbai)
    "ap-southeast-1",  # Southeast Asia (Singapore)
    "ap-northeast-1",  # Northeast Asia (Tokyo)
    "ap-northeast-2",  # Northeast Asia (Seoul)
    "ap-southeast-2",  # Oceania (Sydney)
    "sa-east-1",  # South America (São Paulo)
]


def find_config_file(env_file: str = ".env") -> str | None:
    """Find the specified env file in order of precedence:
    1. Current working directory (where command is run)
    2. Global config:
       - Windows: %APPDATA%/supabase-mcp/{env_file}
       - macOS/Linux: ~/.config/supabase-mcp/{env_file}

    Args:
        env_file: The name of the environment file to look for (default: ".env")

    Returns:
        The path to the found config file, or None if not found
    """
    # 1. Check current directory
    cwd_config = Path.cwd() / env_file
    if cwd_config.exists():
        return str(cwd_config)

    # 2. Check global config
    home = Path.home()
    if os.name == "nt":  # Windows
        global_config = Path(os.environ.get("APPDATA", "")) / "supabase-mcp" / ".env"
    else:  # macOS/Linux
        global_config = home / ".config" / "supabase-mcp" / ".env"

    if global_config.exists():
        return str(global_config)

    return None


class Settings(BaseSettings):
    """Initializes settings for Supabase MCP server."""

    supabase_project_ref: str = Field(
        default="127.0.0.1:54322",  # Local Supabase default
        description="Supabase project ref",
        alias="SUPABASE_PROJECT_REF",
    )
    supabase_db_password: str = Field(
        default="postgres",  # Local Supabase default
        description="Supabase db password",
        alias="SUPABASE_DB_PASSWORD",
    )
    supabase_region: str = Field(
        default="us-east-1",  # East US (North Virginia) - Supabase's default region
        description="Supabase region for connection",
        alias="SUPABASE_REGION",
    )
    supabase_access_token: str | None = Field(
        default=None,
        description="Optional personal access token for accessing Supabase Management API",
        alias="SUPABASE_ACCESS_TOKEN",
    )
    supabase_service_role_key: str | None = Field(
        default=None,
        description="Optional service role key for accessing Python SDK",
        alias="SUPABASE_SERVICE_ROLE_KEY",
    )

    supabase_api_url: str = Field(
        default="https://api.supabase.com",
        description="Supabase API URL",
    )

    query_api_key: str = Field(
        default="test-key",
        description="TheQuery.dev API key",
        alias="QUERY_API_KEY",
    )

    query_api_url: str = Field(
        default="https://api.thequery.dev/v1",
        description="TheQuery.dev API URL",
        alias="QUERY_API_URL",
    )

    @field_validator("supabase_region")
    @classmethod
    def validate_region(cls, v: str, info: ValidationInfo) -> str:
        """Validate that the region is supported by Supabase."""
        # Get the project_ref from the values
        values = info.data
        project_ref = values.get("supabase_project_ref", "")

        # If this is a remote project and region is the default
        if not project_ref.startswith("127.0.0.1") and v == "us-east-1" and "SUPABASE_REGION" not in os.environ:
            logger.warning(
                "IMPORTANT: You're connecting to a remote Supabase project but haven't specified a region. "
                "Using default 'us-east-1', which may cause 'Tenant or user not found' errors if incorrect. "
                "Please set the correct SUPABASE_REGION in your configuration."
            )

        # Validate that the region is supported
        if v not in SUPPORTED_REGIONS.__args__:
            supported = "\n  - ".join([""] + list(SUPPORTED_REGIONS.__args__))
            raise ValueError(f"Region '{v}' is not supported. Supported regions are:{supported}")
        return v

    @classmethod
    def with_config(cls, config_file: str | None = None) -> "Settings":
        """Create Settings with a specific config file.

        Args:
            config_file: Path to .env file to use, or None for no config file
        """

        # Create a new Settings class with the specific config
        class SettingsWithConfig(cls):
            model_config = SettingsConfigDict(env_file=config_file, env_file_encoding="utf-8")

        instance = SettingsWithConfig()

        # Log configuration source and precedence - simplified to a single clear message
        env_vars_present = any(var in os.environ for var in ["SUPABASE_PROJECT_REF", "SUPABASE_DB_PASSWORD"])

        if env_vars_present and config_file:
            logger.info(f"Using environment variables (highest precedence) over config file: {config_file}")
        elif env_vars_present:
            logger.info("Using environment variables for configuration")
        elif config_file:
            logger.info(f"Using settings from config file: {config_file}")
        else:
            logger.info("Using default settings (local development)")

        return instance


# Module-level singleton - maintains existing interface
settings = Settings.with_config(find_config_file())

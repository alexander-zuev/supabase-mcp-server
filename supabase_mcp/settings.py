import os
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
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


def find_config_file() -> str | None:
    """Find the .env file in order of precedence:
    1. Current working directory (where command is run)
    2. Global config:
       - Windows: %APPDATA%/supabase-mcp/.env
       - macOS/Linux: ~/.config/supabase-mcp/.env
    """
    logger.info("Searching for configuration files...")

    # 1. Check current directory
    cwd_config = Path.cwd() / ".env"
    if cwd_config.exists():
        logger.info(f"Found local config file: {cwd_config}")
        return str(cwd_config)

    # 2. Check global config
    home = Path.home()
    if os.name == "nt":  # Windows
        global_config = Path(os.environ.get("APPDATA", "")) / "supabase-mcp" / ".env"
    else:  # macOS/Linux
        global_config = home / ".config" / "supabase-mcp" / ".env"

    if global_config.exists():
        logger.info(f"Found global config file: {global_config}")
        return str(global_config)

    logger.warning("No config files found, using default settings")
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
        default="eu-central-1",  # West EU (Ireland) - Supabase's default region
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

    @field_validator("supabase_region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        """Validate that the region is supported by Supabase."""
        if v not in SUPPORTED_REGIONS.__args__:
            supported = "\n  - ".join([""] + list(SUPPORTED_REGIONS.__args__))
            raise ValueError(f"Region '{v}' is not supported. Supported regions are:{supported}")
        return v

    @classmethod
    def with_config(cls, config_file: str | None = None) -> "Settings":
        """Create Settings with specific config file.

        Args:
            config_file: Path to .env file to use, or None for no config file
        """

        # Create a new Settings class with the specific config
        class SettingsWithConfig(cls):
            model_config = SettingsConfigDict(env_file=config_file, env_file_encoding="utf-8")

        instance = SettingsWithConfig()

        # Log configuration source and precedence
        env_vars_present = any(var in os.environ for var in ["SUPABASE_PROJECT_REF", "SUPABASE_DB_PASSWORD"])

        if env_vars_present:
            logger.warning("Using environment variables (highest precedence)")
            if config_file:
                logger.warning(f"Note: Config file {config_file} exists but environment variables take precedence")
            for var in ["SUPABASE_PROJECT_REF", "SUPABASE_DB_PASSWORD"]:
                if var in os.environ:
                    logger.info(f"Using {var} from environment")
        elif config_file:
            logger.info(f"Using settings from config file: {config_file}")
        else:
            logger.info("Using default settings (local development)")

        # Log final configuration
        logger.info("Final configuration:")
        logger.info(f"  Project ref: {instance.supabase_project_ref}")
        logger.info(f"  Password: {'*' * len(instance.supabase_db_password)}")
        logger.info(f"  Region: {instance.supabase_region}")
        logger.info(
            f"  Service role key: {'*' * len(instance.supabase_service_role_key) if instance.supabase_service_role_key else 'Not set'}"
        )
        return instance


# Module-level singleton - maintains existing interface
settings = Settings.with_config(find_config_file())

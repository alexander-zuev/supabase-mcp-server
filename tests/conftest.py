import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from supabase_mcp.clients.management_client import ManagementAPIClient
from supabase_mcp.clients.sdk_client import SupabaseSDKClient
from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.logger import logger
from supabase_mcp.services.api.api_manager import SupabaseApiManager
from supabase_mcp.services.api.spec_manager import ApiSpecManager
from supabase_mcp.services.database.migration_manager import MigrationManager
from supabase_mcp.services.database.postgres_client import PostgresClient
from supabase_mcp.services.database.query_manager import QueryManager
from supabase_mcp.services.database.sql.loader import SQLLoader
from supabase_mcp.services.database.sql.validator import SQLValidator
from supabase_mcp.services.safety.safety_manager import SafetyManager
from supabase_mcp.settings import Settings, find_config_file
from supabase_mcp.tools import ToolManager
from supabase_mcp.tools.registry import ToolRegistry

# ======================
# Environment Fixtures
# ======================


@pytest.fixture
def clean_environment() -> Generator[None, None, None]:
    """Fixture to provide a clean environment without any Supabase-related env vars."""
    # Save original environment
    original_env = dict(os.environ)

    # Remove all Supabase-related environment variables
    for key in list(os.environ.keys()):
        if key.startswith("SUPABASE_"):
            del os.environ[key]

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


def load_test_env() -> dict[str, str | None]:
    """Load test environment variables from .env.test file"""
    env_test_path = Path(__file__).parent.parent / ".env.test"
    if not env_test_path.exists():
        raise FileNotFoundError(f"Test environment file not found at {env_test_path}")

    load_dotenv(env_test_path)
    return {
        "SUPABASE_PROJECT_REF": os.getenv("SUPABASE_PROJECT_REF"),
        "SUPABASE_DB_PASSWORD": os.getenv("SUPABASE_DB_PASSWORD"),
        "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        "SUPABASE_ACCESS_TOKEN": os.getenv("SUPABASE_ACCESS_TOKEN"),
    }


@pytest.fixture(scope="session")
def settings_integration() -> Settings:
    """Fixture providing settings for integration tests.

    This fixture loads settings from environment variables or .env.test file.
    Uses session scope since settings don't change during tests.
    """
    return Settings.with_config(find_config_file(".env.test"))


@pytest.fixture
def mock_validator() -> SQLValidator:
    """Fixture providing a mock SQLValidator for integration tests."""
    return SQLValidator()


@pytest.fixture
def settings_integration_custom_env() -> Generator[Settings, None, None]:
    """Fixture that provides Settings instance for integration tests using .env.test"""

    # Load custom environment variables
    test_env = load_test_env()
    original_env = dict(os.environ)

    # Set up test environment
    for key, value in test_env.items():
        if value is not None:
            os.environ[key] = value

    # Create fresh settings instance
    settings = Settings()
    logger.info(f"Custom connection settings initialized: {settings}")

    yield settings

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# ======================
# Service Fixtures
# ======================


@pytest_asyncio.fixture(scope="module")
async def postgres_client_integration(settings_integration: Settings) -> AsyncGenerator[PostgresClient, None]:
    # Reset before creation
    await PostgresClient.reset()

    # Create a client
    client = PostgresClient(settings=settings_integration)

    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture(scope="module")
async def spec_manager_integration() -> AsyncGenerator[ApiSpecManager, None]:
    """Fixture providing an ApiSpecManager instance for tests."""
    manager = ApiSpecManager()
    yield manager


@pytest_asyncio.fixture(scope="module")
async def api_client_integration(settings_integration: Settings) -> AsyncGenerator[ManagementAPIClient, None]:
    # We don't need to reset since it's not a singleton
    client = ManagementAPIClient(settings=settings_integration)

    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture(scope="module")
async def sdk_client_integration(settings_integration: Settings) -> AsyncGenerator[SupabaseSDKClient, None]:
    """Fixture providing a SupabaseSDKClient instance for tests.

    Uses function scope to ensure a fresh client for each test.
    """
    client = SupabaseSDKClient.get_instance(settings=settings_integration)
    try:
        yield client
    finally:
        # Reset the singleton to ensure a fresh client for the next test
        SupabaseSDKClient.reset()


@pytest.fixture(scope="module")
def safety_manager_integration() -> SafetyManager:
    """Fixture providing a safety manager for integration tests."""
    # Reset the safety manager singleton
    SafetyManager.reset()

    # Create a new safety manager
    safety_manager = SafetyManager.get_instance()
    safety_manager.register_safety_configs()

    return safety_manager


@pytest.fixture(scope="module")
def tool_manager_integration() -> ToolManager:
    """Fixture providing a tool manager for integration tests."""
    # Reset the tool manager singleton
    ToolManager.reset()
    return ToolManager.get_instance()


@pytest.fixture(scope="module")
def query_manager_integration(
    postgres_client_integration: PostgresClient,
    safety_manager_integration: SafetyManager,
) -> QueryManager:
    """Fixture providing a query manager for integration tests."""
    query_manager = QueryManager(
        postgres_client=postgres_client_integration,
        safety_manager=safety_manager_integration,
    )
    return query_manager


@pytest.fixture(scope="module")
def mock_api_manager() -> SupabaseApiManager:
    """Fixture providing a properly mocked API manager for unit tests."""
    # Create mock dependencies
    mock_client = MagicMock()
    mock_safety_manager = MagicMock()
    mock_spec_manager = MagicMock()

    # Create the API manager with proper constructor arguments
    api_manager = SupabaseApiManager(api_client=mock_client, safety_manager=mock_safety_manager)

    # Add the spec_manager attribute
    api_manager.spec_manager = mock_spec_manager

    return api_manager


@pytest.fixture
def mock_query_manager() -> QueryManager:
    """Fixture providing a properly mocked Query manager for unit tests."""
    # Create mock dependencies
    mock_safety_manager = MagicMock()
    mock_postgres_client = MagicMock()
    mock_validator = MagicMock()

    # Create the Query manager with proper constructor arguments
    query_manager = QueryManager(
        postgres_client=mock_postgres_client,
        safety_manager=mock_safety_manager,
    )

    # Replace the validator with a mock
    query_manager.validator = mock_validator

    # Store the postgres client as an attribute for tests to access
    query_manager.db_client = mock_postgres_client

    # Make execute_query_async an AsyncMock
    query_manager.db_client.execute_query_async = AsyncMock()

    return query_manager


@pytest_asyncio.fixture(scope="module")
async def api_manager_integration(
    api_client_integration: ManagementAPIClient,
    safety_manager_integration: SafetyManager,
) -> AsyncGenerator[SupabaseApiManager, None]:
    """Fixture providing an API manager for integration tests."""

    # Create a new API manager
    api_manager = SupabaseApiManager.get_instance(
        api_client=api_client_integration,
        safety_manager=safety_manager_integration,
    )

    try:
        yield api_manager
    finally:
        # Reset the API manager singleton
        SupabaseApiManager.reset()


# ======================
# Mock MCP Server
# ======================


@pytest.fixture
def mock_mcp_server() -> Any:
    """Fixture providing a mock MCP server for integration tests."""

    # Create a simple mock MCP server that mimics the FastMCP interface
    class MockMCP:
        def __init__(self) -> None:
            self.tools: dict[str, Any] = {}
            self.name = "mock_mcp"

        def register_tool(self, name: str, func: Any, **kwargs: Any) -> None:
            """Register a tool with the MCP server."""
            self.tools[name] = func

        def run(self) -> None:
            """Mock run method."""
            pass

    return MockMCP()


@pytest.fixture(scope="module")
def mock_mcp_server_integration() -> Any:
    """Fixture providing a mock MCP server for integration tests."""
    return FastMCP(name="supabase")


# ======================
# Container Fixture
# ======================


@pytest.fixture(scope="module")
def container_integration(
    postgres_client_integration: PostgresClient,
    api_client_integration: ManagementAPIClient,
    sdk_client_integration: SupabaseSDKClient,
    api_manager_integration: SupabaseApiManager,
    safety_manager_integration: SafetyManager,
    query_manager_integration: QueryManager,
    tool_manager_integration: ToolManager,
    mock_mcp_server_integration: FastMCP,
) -> ServicesContainer:
    """Fixture providing a basic Container for integration tests.

    This container includes all services needed for integration testing,
    but is not initialized.
    """
    # Create a new container with all the services
    container = ServicesContainer(
        mcp_server=mock_mcp_server_integration,
        postgres_client=postgres_client_integration,
        api_client=api_client_integration,
        sdk_client=sdk_client_integration,
        api_manager=api_manager_integration,
        safety_manager=safety_manager_integration,
        query_manager=query_manager_integration,
        tool_manager=tool_manager_integration,
    )

    logger.info("✓ Integration container created successfully.")

    return container


@pytest.fixture(scope="module")
def initialized_container_integration(
    container_integration: ServicesContainer,
    settings_integration: Settings,
) -> ServicesContainer:
    """Fixture providing a fully initialized Container for integration tests.

    This container is initialized with all services and ready to use.
    """
    container_integration.initialize_services(settings_integration)
    logger.info("✓ Integration container initialized successfully.")

    return container_integration


@pytest.fixture(scope="module")
def tools_registry_integration(
    initialized_container_integration: ServicesContainer,
) -> ServicesContainer:
    """Fixture providing a Container with tools registered for integration tests.

    This container has all tools registered with the MCP server.
    """
    container = initialized_container_integration
    mcp_server = container.mcp_server

    registry = ToolRegistry(mcp_server, container)
    registry.register_tools()

    logger.info("✓ Tools registered with MCP server successfully.")

    return container


@pytest.fixture
def sql_loader() -> SQLLoader:
    """Fixture providing a SQLLoader instance for tests."""
    return SQLLoader()


@pytest.fixture
def migration_manager(sql_loader: SQLLoader) -> MigrationManager:
    """Fixture providing a MigrationManager instance for tests."""
    return MigrationManager(loader=sql_loader)

from typing import Any, cast

from mcp.server.fastmcp import FastMCP

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.settings import Settings


class TestContainer:
    """Tests for the Container class functionality."""

    def test_container_initialization(self, container_integration: ServicesContainer):
        """Test that the container is properly initialized with all services."""
        # Verify all services are properly initialized
        assert container_integration.postgres_client is not None
        assert container_integration.api_client is not None
        assert container_integration.sdk_client is not None
        assert container_integration.api_manager is not None
        assert container_integration.safety_manager is not None
        assert container_integration.query_manager is not None
        assert container_integration.tool_manager is not None
        assert container_integration.mcp_server is not None

    def test_container_initialize_method(self, settings_integration: Settings, mock_mcp_server: Any):
        """Test the initialize method creates all services properly."""
        # Create empty container
        container = ServicesContainer(mcp_server=cast(FastMCP, mock_mcp_server))

        # Initialize with settings
        container.initialize_services(settings_integration)

        # Verify all services were created
        assert container.postgres_client is not None
        assert container.api_client is not None
        assert container.sdk_client is not None
        assert container.api_manager is not None
        assert container.safety_manager is not None
        assert container.query_manager is not None
        assert container.tool_manager is not None
        assert container.mcp_server is not None

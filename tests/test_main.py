import asyncio
import subprocess
from unittest.mock import patch

import pytest

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.logger import logger
from supabase_mcp.main import run_inspector, run_server
from supabase_mcp.services.safety.models import ClientType
from supabase_mcp.tools.manager import ToolName

# === UNIT TESTS ===


class TestMain:
    """Tests for the main application functionality."""

    @pytest.mark.unit
    def test_mcp_server_initializes(self, container_integration: ServicesContainer):
        """Test that the MCP server initializes correctly."""
        # Verify server name
        mcp = container_integration.mcp_server
        assert mcp.name == "supabase"

        # Verify MCP server is created but not yet initialized with tools
        tools = asyncio.run(mcp.list_tools())
        logger.info(f"Found {len(tools)} MCP tools registered in basic container")

        # At this point, no tools should be registered yet
        assert len(tools) == 0, f"Expected 0 tools in basic container, but got {len(tools)}"

    @pytest.mark.unit
    def test_services_container_initialization(
        self,
        initialized_container_integration: ServicesContainer,
    ):
        """Test that the services container is correctly initialized."""
        # Verify container has all required services
        container = initialized_container_integration
        assert container.postgres_client is not None
        assert container.api_client is not None
        assert container.sdk_client is not None
        assert container.api_manager is not None
        assert container.safety_manager is not None
        assert container.query_manager is not None
        assert container.tool_manager is not None

        # Verify the container is fully initialized
        # Check that safety manager has been initialized by verifying it has configs registered
        safety_manager = container.safety_manager
        assert safety_manager.get_safety_mode(ClientType.DATABASE) is not None
        assert safety_manager.get_safety_mode(ClientType.API) is not None

    @pytest.mark.unit
    def test_tool_registration(self, tools_registry_integration: ServicesContainer):
        """Test that tools are registered correctly using ToolManager's tool names."""

        # Get the tool manager from the container
        tool_manager = tools_registry_integration.tool_manager
        assert tool_manager is not None, "Tool manager should be initialized"

        # Get the MCP server from the container
        mcp = tools_registry_integration.mcp_server

        # Get expected tools from ToolName enum
        expected_tools = [
            ToolName.GET_SCHEMAS,
            ToolName.GET_TABLES,
            ToolName.GET_TABLE_SCHEMA,
            ToolName.EXECUTE_POSTGRESQL,
            ToolName.CONFIRM_DESTRUCTIVE_OPERATION,
            ToolName.RETRIEVE_MIGRATIONS,
            ToolName.LIVE_DANGEROUSLY,
            ToolName.SEND_MANAGEMENT_API_REQUEST,
            ToolName.GET_MANAGEMENT_API_SPEC,
            ToolName.GET_AUTH_ADMIN_METHODS_SPEC,
            ToolName.CALL_AUTH_ADMIN_METHOD,
            ToolName.RETRIEVE_LOGS,
        ]

        # Verify tools are registered in MCP
        registered_tools = asyncio.run(mcp.list_tools())
        registered_tool_names = {tool.name for tool in registered_tools}

        # We should have exactly 12 tools (all the tools defined in ToolName enum)
        assert len(registered_tools) == 12, f"Expected 12 tools, but got {len(registered_tools)}"

        # Log the actual number of tools for reference
        logger.info(f"Found {len(registered_tools)} MCP tools registered")

        # Verify each tool has proper MCP protocol structure
        for tool in registered_tools:
            assert tool.name, "Tool must have a name"
            assert tool.description, "Tool must have a description"
            assert tool.inputSchema, "Tool must have an input schema"

        # Check that each expected tool is registered by its string value
        for tool_name in expected_tools:
            # Convert enum to string value (e.g., 'get_schemas' instead of ToolName.GET_SCHEMAS)
            tool_str_value = str(tool_name.value)
            assert tool_str_value in registered_tool_names, f"Tool {tool_name} not registered"

        # Verify we have tools for core functionality categories
        # Instead of checking specific names, check for categories of functionality
        tool_names = {tool.name for tool in registered_tools}

        # Log all available tools for debugging
        tool_list = ", ".join(sorted(tool_names))
        logger.info(f"Available MCP tools: {tool_list}")

    @pytest.mark.unit
    def test_run_server_starts(self):
        """Test that run_server starts the server."""
        # Patch the global mcp instance and its run method
        with patch("supabase_mcp.main.mcp") as mock_mcp:
            # Call run_server which should use the global mcp instance
            run_server()
            mock_mcp.run.assert_called_once()

    @pytest.mark.unit
    def test_inspector_mode(self):
        """Test that inspector mode initializes correctly"""
        # This test is fine as is since it's testing the global function
        # and mocking an external dependency
        with patch("mcp.cli.cli.dev") as mock_dev:
            # Patch __file__ in the main module to match what we expect
            with patch("supabase_mcp.main.__file__", __file__):
                run_inspector()
                mock_dev.assert_called_once_with(__file__)

    @pytest.mark.unit
    def test_server_command_starts(self):
        """Test that the server command executes without errors"""
        import os

        # Skip this test in CI environments
        if os.environ.get("CI") == "true":
            pytest.skip("Skipping server start test in CI environment")

        result = subprocess.run(
            ["supabase-mcp-server"],
            capture_output=True,
            text=True,
            timeout=2,  # Kill after 2 seconds since it's a server
        )
        assert result.returncode == 0, f"Server command failed: {result.stderr}"

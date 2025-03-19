from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.services.database.postgres_client import QueryResult
from supabase_mcp.tools.manager import ToolName


class ToolRegistry:
    """Responsible for registering tools with the MCP server"""

    def __init__(self, mcp: FastMCP, services_container: ServicesContainer):
        self.mcp = mcp
        self.services_container = services_container

    def register_tools(self) -> FastMCP:
        """Register all tools with the MCP server"""
        mcp = self.mcp
        services_container = self.services_container

        tool_manager = services_container.tool_manager
        feature_manager = services_container.feature_manager

        @mcp.tool(description=tool_manager.get_description(ToolName.GET_SCHEMAS))  # type: ignore
        async def get_schemas() -> QueryResult:
            """List all database schemas with their sizes and table counts."""
            return await feature_manager.execute_tool(ToolName.GET_SCHEMAS, services_container=services_container)

        @mcp.tool(description=tool_manager.get_description(ToolName.GET_TABLES))  # type: ignore
        async def get_tables(schema_name: str) -> QueryResult:
            """List all tables, foreign tables, and views in a schema with their sizes, row counts, and metadata."""
            return await feature_manager.execute_tool(
                ToolName.GET_TABLES, services_container=services_container, schema_name=schema_name
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.GET_TABLE_SCHEMA))  # type: ignore
        async def get_table_schema(schema_name: str, table: str) -> QueryResult:
            """Get detailed table structure including columns, keys, and relationships."""
            return await feature_manager.execute_tool(
                ToolName.GET_TABLE_SCHEMA,
                services_container=services_container,
                schema_name=schema_name,
                table=table,
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.EXECUTE_POSTGRESQL))  # type: ignore
        async def execute_postgresql(query: str, migration_name: str = "") -> QueryResult:
            """Execute PostgreSQL statements against your Supabase database."""
            return await feature_manager.execute_tool(
                ToolName.EXECUTE_POSTGRESQL,
                services_container=services_container,
                query=query,
                migration_name=migration_name,
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.RETRIEVE_MIGRATIONS))  # type: ignore
        async def retrieve_migrations(
            limit: int = 50,
            offset: int = 0,
            name_pattern: str = "",
            include_full_queries: bool = False,
        ) -> QueryResult:
            """Retrieve a list of all migrations a user has from Supabase.

            SAFETY: This is a low-risk read operation that can be executed in SAFE mode.
            """

            result = await feature_manager.execute_tool(
                ToolName.RETRIEVE_MIGRATIONS,
                services_container=services_container,
                limit=limit,
                offset=offset,
                name_pattern=name_pattern,
                include_full_queries=include_full_queries,
            )
            return QueryResult.model_validate(result)

        @mcp.tool(description=tool_manager.get_description(ToolName.SEND_MANAGEMENT_API_REQUEST))  # type: ignore
        async def send_management_api_request(
            method: str,
            path: str,
            path_params: dict[str, str],
            request_params: dict[str, Any],
            request_body: dict[str, Any],
        ) -> dict[str, Any]:
            """Execute a Supabase Management API request."""
            return await feature_manager.execute_tool(
                ToolName.SEND_MANAGEMENT_API_REQUEST,
                services_container=services_container,
                method=method,
                path=path,
                path_params=path_params,
                request_params=request_params,
                request_body=request_body,
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.GET_MANAGEMENT_API_SPEC))  # type: ignore
        async def get_management_api_spec(params: dict[str, Any] = {}) -> dict[str, Any]:
            """Get the Supabase Management API specification.

            This tool can be used in four different ways (and then some ;)):
            1. Without parameters: Returns all domains (default)
            2. With path and method: Returns the full specification for a specific API endpoint
            3. With domain only: Returns all paths and methods within that domain
            4. With all_paths=True: Returns all paths and methods

            Args:
                params: Dictionary containing optional parameters:
                    - path: Optional API path (e.g., "/v1/projects/{ref}/functions")
                    - method: Optional HTTP method (e.g., "GET", "POST")
                    - domain: Optional domain/tag name (e.g., "Auth", "Storage")
                    - all_paths: If True, returns all paths and methods

            Returns:
                API specification based on the provided parameters
            """
            return await feature_manager.execute_tool(
                ToolName.GET_MANAGEMENT_API_SPEC, services_container=services_container, params=params
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.GET_AUTH_ADMIN_METHODS_SPEC))  # type: ignore
        async def get_auth_admin_methods_spec() -> dict[str, Any]:
            """Get Python SDK methods specification for Auth Admin."""
            return await feature_manager.execute_tool(
                ToolName.GET_AUTH_ADMIN_METHODS_SPEC, services_container=services_container
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.CALL_AUTH_ADMIN_METHOD))  # type: ignore
        async def call_auth_admin_method(method: str, params: dict[str, Any]) -> dict[str, Any]:
            """Call an Auth Admin method from Supabase Python SDK."""
            return await feature_manager.execute_tool(
                ToolName.CALL_AUTH_ADMIN_METHOD, services_container=services_container, method=method, params=params
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.LIVE_DANGEROUSLY))  # type: ignore
        async def live_dangerously(
            service: Literal["api", "database"], enable_unsafe_mode: bool = False
        ) -> dict[str, Any]:
            """
            Toggle between safe and unsafe operation modes for API or Database services.

            This function controls the safety level for operations, allowing you to:
            - Enable write operations for the database (INSERT, UPDATE, DELETE, schema changes)
            - Enable state-changing operations for the Management API
            """
            return await feature_manager.execute_tool(
                ToolName.LIVE_DANGEROUSLY,
                services_container=services_container,
                service=service,
                enable_unsafe_mode=enable_unsafe_mode,
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.CONFIRM_DESTRUCTIVE_OPERATION))  # type: ignore
        async def confirm_destructive_operation(
            operation_type: Literal["api", "database"], confirmation_id: str, user_confirmation: bool = False
        ) -> QueryResult | dict[str, Any]:
            """Execute a destructive operation after confirmation. Use this only after reviewing the risks with the user."""
            return await feature_manager.execute_tool(
                ToolName.CONFIRM_DESTRUCTIVE_OPERATION,
                services_container=services_container,
                operation_type=operation_type,
                confirmation_id=confirmation_id,
                user_confirmation=user_confirmation,
            )

        @mcp.tool(description=tool_manager.get_description(ToolName.RETRIEVE_LOGS))  # type: ignore
        async def retrieve_logs(
            collection: str,
            limit: int = 20,
            hours_ago: int = 1,
            filters: list[dict[str, Any]] = [],
            search: str = "",
            custom_query: str = "",
        ) -> dict[str, Any]:
            """Retrieve logs from your Supabase project's services for debugging and monitoring."""
            return await feature_manager.execute_tool(
                ToolName.RETRIEVE_LOGS,
                services_container=services_container,
                collection=collection,
                limit=limit,
                hours_ago=hours_ago,
                filters=filters,
                search=search,
                custom_query=custom_query,
            )

        return mcp

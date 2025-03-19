from typing import TYPE_CHECKING, Any, Literal

from supabase_mcp.clients.api_client import ApiClient
from supabase_mcp.exceptions import APIError, ConfirmationRequiredError, FeatureAccessError, FeatureTemporaryError
from supabase_mcp.logger import logger
from supabase_mcp.services.database.postgres_client import QueryResult
from supabase_mcp.services.safety.models import ClientType, SafetyMode
from supabase_mcp.tools.manager import ToolName

if TYPE_CHECKING:
    from supabase_mcp.core.container import ServicesContainer


class FeatureManager:
    """Service for managing features, access to them and their configuration."""

    def __init__(self, api_client: ApiClient):
        """Initialize the feature service.

        Args:
            api_client: Client for communicating with the API
        """
        self.api_client = api_client

    async def check_feature_access(self, feature_name: str) -> None:
        """Check if the user has access to a feature.

        Args:
            feature_name: Name of the feature to check

        Raises:
            FeatureAccessError: If the user doesn't have access to the feature
        """
        try:
            # Use the API client to check feature access
            response = await self.api_client.check_feature_access(feature_name)

            # If access is not granted, raise an exception
            if not response.access_granted:
                logger.info(f"Feature access denied: {feature_name}")
                raise FeatureAccessError(feature_name)

            logger.debug(f"Feature access granted: {feature_name}")

        except APIError as e:
            logger.error(f"API error checking feature access: {feature_name} - {e}")
            raise FeatureTemporaryError(feature_name, e.status_code, e.response_body) from e
        except Exception as e:
            if not isinstance(e, FeatureAccessError):
                logger.error(f"Unexpected error checking feature access: {feature_name} - {e}")
                raise FeatureTemporaryError(feature_name) from e
            raise

    async def execute_tool(self, tool_name: ToolName, services_container: "ServicesContainer", **kwargs: Any) -> Any:
        """Execute a tool with feature access check.

        Args:
            tool_name: Name of the tool to execute
            services_container: Container with all services
            **kwargs: Arguments to pass to the tool

        Returns:
            Result of the tool execution
        """
        # Check feature access
        await self.check_feature_access(tool_name.value)

        # Execute the appropriate tool based on name
        if tool_name == ToolName.GET_SCHEMAS:
            return await self.get_schemas(services_container)
        elif tool_name == ToolName.GET_TABLES:
            return await self.get_tables(services_container, **kwargs)
        elif tool_name == ToolName.GET_TABLE_SCHEMA:
            return await self.get_table_schema(services_container, **kwargs)
        elif tool_name == ToolName.EXECUTE_POSTGRESQL:
            return await self.execute_postgresql(services_container, **kwargs)
        elif tool_name == ToolName.RETRIEVE_MIGRATIONS:
            return await self.retrieve_migrations(services_container, **kwargs)
        elif tool_name == ToolName.SEND_MANAGEMENT_API_REQUEST:
            return await self.send_management_api_request(services_container, **kwargs)
        elif tool_name == ToolName.GET_MANAGEMENT_API_SPEC:
            return await self.get_management_api_spec(services_container, **kwargs)
        elif tool_name == ToolName.GET_AUTH_ADMIN_METHODS_SPEC:
            return await self.get_auth_admin_methods_spec(services_container)
        elif tool_name == ToolName.CALL_AUTH_ADMIN_METHOD:
            return await self.call_auth_admin_method(services_container, **kwargs)
        elif tool_name == ToolName.LIVE_DANGEROUSLY:
            return await self.live_dangerously(services_container, **kwargs)
        elif tool_name == ToolName.CONFIRM_DESTRUCTIVE_OPERATION:
            return await self.confirm_destructive_operation(services_container, **kwargs)
        elif tool_name == ToolName.RETRIEVE_LOGS:
            return await self.retrieve_logs(services_container, **kwargs)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    async def get_schemas(self, container: "ServicesContainer") -> QueryResult:
        """List all database schemas with their sizes and table counts."""
        query_manager = container.query_manager
        query = query_manager.get_schemas_query()
        return await query_manager.handle_query(query)

    async def get_tables(self, container: "ServicesContainer", schema_name: str) -> QueryResult:
        """List all tables, foreign tables, and views in a schema with their sizes, row counts, and metadata."""
        query_manager = container.query_manager
        query = query_manager.get_tables_query(schema_name)
        return await query_manager.handle_query(query)

    async def get_table_schema(self, container: "ServicesContainer", schema_name: str, table: str) -> QueryResult:
        """Get detailed table structure including columns, keys, and relationships."""
        query_manager = container.query_manager
        query = query_manager.get_table_schema_query(schema_name, table)
        return await query_manager.handle_query(query)

    async def execute_postgresql(
        self, container: "ServicesContainer", query: str, migration_name: str = ""
    ) -> QueryResult:
        """Execute PostgreSQL statements against your Supabase database."""
        query_manager = container.query_manager
        return await query_manager.handle_query(query, has_confirmation=False, migration_name=migration_name)

    async def retrieve_migrations(
        self,
        container: "ServicesContainer",
        limit: int = 50,
        offset: int = 0,
        name_pattern: str = "",
        include_full_queries: bool = False,
    ) -> QueryResult:
        """Retrieve a list of all migrations a user has from Supabase."""
        query_manager = container.query_manager
        query = query_manager.get_migrations_query(
            limit=limit, offset=offset, name_pattern=name_pattern, include_full_queries=include_full_queries
        )
        return await query_manager.handle_query(query)

    async def send_management_api_request(
        self,
        container: "ServicesContainer",
        method: str,
        path: str,
        path_params: dict[str, str],
        request_params: dict[str, Any],
        request_body: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Supabase Management API request."""
        api_manager = container.api_manager
        return await api_manager.execute_request(method, path, path_params, request_params, request_body)

    async def get_management_api_spec(
        self, container: "ServicesContainer", params: dict[str, Any] = {}
    ) -> dict[str, Any]:
        """Get the Supabase Management API specification."""
        path = params.get("path")
        method = params.get("method")
        domain = params.get("domain")
        all_paths = params.get("all_paths", False)

        logger.debug(
            f"Getting management API spec with path: {path}, method: {method}, domain: {domain}, all_paths: {all_paths}"
        )
        api_manager = container.api_manager
        return await api_manager.handle_spec_request(path, method, domain, all_paths)

    async def get_auth_admin_methods_spec(self, container: "ServicesContainer") -> dict[str, Any]:
        """Get Python SDK methods specification for Auth Admin."""
        sdk_client = container.sdk_client
        return sdk_client.return_python_sdk_spec()

    async def call_auth_admin_method(
        self, container: "ServicesContainer", method: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Call an Auth Admin method from Supabase Python SDK."""
        sdk_client = container.sdk_client
        return await sdk_client.call_auth_admin_method(method, params)

    async def live_dangerously(
        self, container: "ServicesContainer", service: Literal["api", "database"], enable_unsafe_mode: bool = False
    ) -> dict[str, Any]:
        """
        Toggle between safe and unsafe operation modes for API or Database services.

        This function controls the safety level for operations, allowing you to:
        - Enable write operations for the database (INSERT, UPDATE, DELETE, schema changes)
        - Enable state-changing operations for the Management API
        """
        safety_manager = container.safety_manager
        if service == "api":
            # Set the safety mode in the safety manager
            new_mode = SafetyMode.UNSAFE if enable_unsafe_mode else SafetyMode.SAFE
            safety_manager.set_safety_mode(ClientType.API, new_mode)

            # Return the actual mode that was set
            return {"service": "api", "mode": safety_manager.get_safety_mode(ClientType.API)}
        elif service == "database":
            # Set the safety mode in the safety manager
            new_mode = SafetyMode.UNSAFE if enable_unsafe_mode else SafetyMode.SAFE
            safety_manager.set_safety_mode(ClientType.DATABASE, new_mode)

            # Return the actual mode that was set
            return {"service": "database", "mode": safety_manager.get_safety_mode(ClientType.DATABASE)}

    async def confirm_destructive_operation(
        self,
        container: "ServicesContainer",
        operation_type: Literal["api", "database"],
        confirmation_id: str,
        user_confirmation: bool = False,
    ) -> QueryResult | dict[str, Any]:
        """Execute a destructive operation after confirmation. Use this only after reviewing the risks with the user."""
        api_manager = container.api_manager
        query_manager = container.query_manager
        if not user_confirmation:
            raise ConfirmationRequiredError("Destructive operation requires explicit user confirmation.")

        if operation_type == "api":
            return await api_manager.handle_confirmation(confirmation_id)
        elif operation_type == "database":
            return await query_manager.handle_confirmation(confirmation_id)

    async def retrieve_logs(
        self,
        container: "ServicesContainer",
        collection: str,
        limit: int = 20,
        hours_ago: int = 1,
        filters: list[dict[str, Any]] = [],
        search: str = "",
        custom_query: str = "",
    ) -> dict[str, Any]:
        """Retrieve logs from your Supabase project's services for debugging and monitoring."""
        logger.info(
            f"Tool called: retrieve_logs(collection={collection}, limit={limit}, hours_ago={hours_ago}, filters={filters}, search={search}, custom_query={'<custom>' if custom_query else None})"
        )

        api_manager = container.api_manager
        result = await api_manager.retrieve_logs(
            collection=collection,
            limit=limit,
            hours_ago=hours_ago,
            filters=filters,
            search=search,
            custom_query=custom_query,
        )

        logger.info(f"Tool completed: retrieve_logs - Retrieved log entries for collection={collection}")

        return result

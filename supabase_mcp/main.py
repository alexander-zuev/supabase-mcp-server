from pathlib import Path
from typing import Literal

from mcp.server.fastmcp import FastMCP

from supabase_mcp.api_manager.api_manager import SupabaseApiManager
from supabase_mcp.api_manager.api_safety_config import SafetyLevel
from supabase_mcp.db_client.db_client import SupabaseClient
from supabase_mcp.db_client.db_safety_config import DbSafetyLevel
from supabase_mcp.logger import logger
from supabase_mcp.queries import PreBuiltQueries
from supabase_mcp.sdk_client.python_client import SupabaseSDKClient
from supabase_mcp.settings import settings
from supabase_mcp.validators import (
    validate_schema_name,
    validate_sql_query,
    validate_table_name,
)

try:
    mcp = FastMCP("supabase")
    supabase = SupabaseClient.create()
except Exception as e:
    logger.error(f"Failed to create Supabase client: {e}")
    raise e


@mcp.tool(description="List all database schemas with their sizes and table counts.")
async def get_db_schemas():
    """Get all accessible database schemas with their total sizes and number of tables."""
    query = PreBuiltQueries.get_schemas_query()
    result = supabase.execute_query(query)
    return result


@mcp.tool(
    description="List all tables, foreign tables, and views in a schema with their sizes, row counts, and metadata."
)
async def get_tables(schema_name: str):
    """Get all tables, foreign tables, and views from a schema with size, row count, column count, and index information."""
    schema_name = validate_schema_name(schema_name)
    query = PreBuiltQueries.get_tables_in_schema_query(schema_name)
    return supabase.execute_query(query)


@mcp.tool(description="Get detailed table structure including columns, keys, and relationships.")
async def get_table_schema(schema_name: str, table: str):
    """Get table schema including column definitions, primary keys, and foreign key relationships."""
    schema_name = validate_schema_name(schema_name)
    table = validate_table_name(table)
    query = PreBuiltQueries.get_table_schema_query(schema_name, table)
    return supabase.execute_query(query)


@mcp.tool(
    description="""
Query the database with a raw SQL query.

IMPORTANT USAGE GUIDELINES:
1. For READ operations (SELECT):
   - Use simple SELECT statements
   - Example: SELECT * FROM public.users LIMIT 10;

2. For WRITE operations (INSERT/UPDATE/DELETE/CREATE/ALTER/DROP):
   - ALWAYS wrap in explicit BEGIN/COMMIT blocks
   - Example:
     BEGIN;
     CREATE TABLE public.test_table (id SERIAL PRIMARY KEY, name TEXT);
     COMMIT;

3. NEVER mix READ and WRITE operations in the same query
4. NEVER use single DDL statements without transaction control
5. Remember to enable unsafe mode first with live_dangerously('database', True)
6. For auth operations (primarily creating, updating, deleting users, generating links, etc), prefer using the Auth Admin SDK methods 
   instead of direct SQL manipulation to ensure correctness and prevent security issues

TRANSACTION HANDLING:
- The server detects BEGIN/COMMIT/ROLLBACK keywords to respect your transaction control
- When you use these keywords, the server will not interfere with your transactions
- For queries without transaction control, the server will auto-commit in write mode

Failure to follow these guidelines will result in errors.
"""
)
async def execute_sql_query(query: str):
    """Execute an SQL query with validation."""
    query = validate_sql_query(query)
    return supabase.execute_query(query)


# Core Tools
@mcp.tool(
    description="""
Execute a Supabase Management API request. Use paths exactly as defined in the API spec -
the {ref} parameter will be automatically injected from settings.

Parameters:
- method: HTTP method (GET, POST, PUT, PATCH, DELETE)
- path: API path (e.g. /v1/projects/{ref}/functions)
- request_params: Query parameters as dict (e.g. {"key": "value"}) - use empty dict {} if not needed
- request_body: Request body as dict (e.g. {"name": "test"}) - use empty dict {} if not needed

Examples:
1. GET request with params:
   method: "GET"
   path: "/v1/projects/{ref}/functions"
   request_params: {"name": "test"}
   request_body: {}

2. POST request with body:
   method: "POST"
   path: "/v1/projects/{ref}/functions"
   request_params: {}
   request_body: {"name": "test-function", "slug": "test-function"}
"""
)
async def send_management_api_request(
    method: str,
    path: str,  # URL path
    request_params: dict,  # Query parameters as dict
    request_body: dict,  # Request body as dict
) -> dict:
    """
    Execute a Management API request.

    Args:
        method: HTTP method (GET, POST, etc)
        path: API path exactly as in spec, {ref} will be auto-injected
        request_params: Query parameters as dict if needed (e.g. {"key": "value"})
        request_body: Request body as dict for POST/PUT/PATCH (e.g. {"name": "test"})

    Example:
        To get a function details, use:
        path="/v1/projects/{ref}/functions/{function_slug}"
        The {ref} will be auto-injected, only function_slug needs to be provided
    """
    api_manager = await SupabaseApiManager.get_manager()
    return await api_manager.execute_request(method, path, request_params, request_body)


@mcp.tool(
    description="""
Toggle unsafe mode for either Management API or Database operations.
In safe mode (default):
- API: only read operations allowed
- Database: only SELECT queries allowed
In unsafe mode:
- API: state-changing operations permitted (except blocked ones)
- Database: all SQL operations permitted
"""
)
async def live_dangerously(service: Literal["api", "database"], enable: bool = False) -> dict:
    """
    Toggle between safe and unsafe operation modes for a specific service.

    Args:
        service: Which service to toggle ("api" or "database")
        enable: True to enable unsafe mode, False for safe mode

    Returns:
        dict: Current mode status for the specified service
    """
    if service == "api":
        api_manager = await SupabaseApiManager.get_manager()
        api_manager.switch_mode(SafetyLevel.UNSAFE if enable else SafetyLevel.SAFE)
        return {"service": "api", "mode": api_manager.mode}
    else:  # database
        supabase.switch_mode(DbSafetyLevel.RW if enable else DbSafetyLevel.RO)
        return {"service": "database", "mode": supabase.mode}


@mcp.tool(
    description="""
Get the latests complete Management API specification.
Use this to understand available operations and their requirements.
"""
)
async def get_management_api_spec() -> dict:
    """
    Get enriched API specification with safety information.

    Returns:
        dict: OpenAPI spec with added safety metadata per operation
    """
    api_manager = await SupabaseApiManager.get_manager()
    return api_manager.get_spec()


@mcp.tool(description="Get all safety rules for the Supabase Management API")
async def get_management_api_safety_rules() -> dict:
    """Returns all safety rules including blocked and unsafe operations with human-readable explanations"""
    api_manager = await SupabaseApiManager.get_manager()
    return api_manager.get_safety_rules()


@mcp.tool(
    description="""
Get Python SDK methods specification for Auth Admin. Returns a python dictionary of all Auth Python SDK methods.
Use this to understand the available methods and their required parameters.
"""
)
async def get_auth_admin_methods_spec() -> dict:
    """Returns the Python SDK spec"""
    sdk_client = await SupabaseSDKClient.get_instance()
    return sdk_client.return_python_sdk_spec()


@mcp.tool(
    description="""
Call an Auth Admin method from Supabase Python SDK. Returns the result of the method call.

Available methods:
- get_user_by_id: Retrieve a user by their ID
- list_users: List all users with pagination
- create_user: Create a new user
- delete_user: Delete a user by their ID
- invite_user_by_email: Send an invite link to a user's email
- generate_link: Generate an email link for various authentication purposes
- update_user_by_id: Update user attributes by ID
- delete_factor: Delete a factor on a user

Each method requires specific parameters. For nested parameters, follow the structure exactly:

Examples:
1. Get user by ID:
   method: "get_user_by_id"
   params: {"uid": "user-uuid-here"}

2. Create user:
   method: "create_user"
   params: {
     "email": "user@example.com",
     "password": "secure-password",
     "email_confirm": true,
     "user_metadata": {"name": "John Doe"}
   }

3. Generate link:
   method: "generate_link"
   params: {
     "params": {
       "type": "signup",
       "email": "user@example.com",
       "password": "secure-password",
       "options": {
         "data": {"name": "John Doe"},
         "redirect_to": "https://example.com/welcome"
       }
     }
   }

Use get_auth_admin_methods_spec() to see full documentation for all methods.
"""
)
async def call_auth_admin_method(method: str, params: dict) -> dict:
    """Calls a method of the Python SDK client"""
    sdk_client = await SupabaseSDKClient.get_instance()
    return await sdk_client.call_auth_admin_method(method, params)


def run():
    """Run the Supabase MCP server."""
    if settings.supabase_project_ref.startswith("127.0.0.1"):
        logger.info(
            "Starting Supabase MCP server to connect to local project: %s",
            settings.supabase_project_ref,
        )
    else:
        logger.info(
            "Starting Supabase MCP server to connect to project ref: %s (region: %s)",
            settings.supabase_project_ref,
            settings.supabase_region,
        )
    if settings.supabase_access_token:
        logger.info("Personal access token detected - using for Management API")
    if settings.supabase_service_role_key:
        logger.info("Service role key detected - using for Python SDK")
    mcp.run()


if __name__ == "__main__":
    run()


def inspector():
    """Inspector mode - same as mcp dev"""
    logger.info("Starting Supabase MCP server inspector")

    import importlib.util

    from mcp.cli.cli import dev  # Import from correct module

    # Get the package location
    spec = importlib.util.find_spec("supabase_mcp")
    if spec and spec.origin:
        package_dir = str(Path(spec.origin).parent)
        file_spec = str(Path(package_dir) / "main.py")
        logger.info(f"Using file spec: {file_spec}")
        return dev(file_spec=file_spec)
    else:
        raise ImportError("Could not find supabase_mcp package")

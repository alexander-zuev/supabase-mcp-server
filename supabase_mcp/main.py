from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.logger import logger
from supabase_mcp.settings import settings
from supabase_mcp.tools.registry import ToolRegistry


# Create lifespan for the MCP server
@asynccontextmanager
async def lifespan(app: FastMCP):
    try:
        # Initialize services
        services_container = ServicesContainer.get_instance()
        services_container.initialize_services(settings)

        # Register tools
        mcp = ToolRegistry(mcp=app, services_container=services_container).register_tools()
        yield mcp
    finally:
        services_container = ServicesContainer.get_instance()
        await services_container.shutdown_services()


# Create mcp instance
mcp = FastMCP("supabase", lifespan=lifespan)


def run_server() -> None:
    logger.info("Starting Supabase MCP server")
    mcp.run()


def run_inspector() -> None:
    """Inspector mode - same as mcp dev"""
    logger.info("Starting Supabase MCP server inspector")

    from mcp.cli.cli import dev

    return dev(__file__)


if __name__ == "__main__":
    logger.info("Starting Supabase MCP server")
    run_server()

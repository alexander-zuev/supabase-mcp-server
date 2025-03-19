import httpx
from pydantic import BaseModel

from supabase_mcp.clients.base_http_client import AsyncHTTPClient
from supabase_mcp.logger import logger
from supabase_mcp.settings import settings


class ApiRoutes:
    """Routes for the Query API"""

    FEATURES_ACCESS = "/features/{feature_name}/access"


class FeatureAccessRequest(BaseModel):
    """Request for feature access. Later can be extended with additional metadata."""

    feature_name: str


class FeatureAccessResponse(BaseModel):
    """Response for feature access. Later can be extended with additional metadata."""

    access_granted: bool


class ApiClient(AsyncHTTPClient):
    """Client for communicating with the Query API server for premium features.

    To preserve backwards compatibility and ensure a smooth UX for existing users,
    API key is not required as of now.
    """

    def __init__(
        self,
        query_api_key: str | None = None,
        query_api_url: str | None = None,
    ):
        """Initialize the Query API client"""
        self.query_api_key = query_api_key or settings.query_api_key
        self.query_api_url = query_api_url or settings.query_api_url
        self._check_api_key_set()
        self.client: httpx.AsyncClient | None = None
        logger.info(f"Query API client initialized with URL: {self.query_api_url}, key: {self.query_api_key}")

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client exists and is ready for use.

        Creates the client if it doesn't exist yet.
        Returns the client instance.
        """
        if self.client is None:
            logger.info("Creating new Query API client")
            self.client = httpx.AsyncClient(
                base_url=self.query_api_url,
                headers={"Authorization": f"Bearer {self.query_api_key}"},
                timeout=30.0,
            )
        logger.info("Returning existing Query API client")
        return self.client

    async def close(self) -> None:
        """Close the client and release resources."""
        if self.client:
            await self.client.aclose()
            logger.info("Query API client closed")

    def _check_api_key_set(self) -> None:
        """Check if the API key is set"""
        if not self.query_api_key:
            logger.warning("Query API key is not set. Only free features will be available.")
            return

    async def check_feature_access(self, feature_name: str) -> FeatureAccessResponse:
        """Check if the feature is available for the user"""

        try:
            result = await self.execute_request(
                method="GET",
                path=ApiRoutes.FEATURES_ACCESS.format(feature_name=feature_name),
            )
            return FeatureAccessResponse.model_validate(result)
        except Exception as e:
            logger.error(f"Error checking feature access: {e}")
            raise e

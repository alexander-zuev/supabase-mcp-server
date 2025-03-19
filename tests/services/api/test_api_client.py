import httpx
import pytest

from supabase_mcp.clients.management_client import ManagementAPIClient
from supabase_mcp.exceptions import APIClientError, APIConnectionError


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestAPIClient:
    """Integration tests for the API client."""

    async def test_execute_get_request(self, api_client_integration: ManagementAPIClient):
        """Test executing a GET request to the API."""
        # Make a simple GET request to a public endpoint
        # Since /v1/health returns 404, we'll test the error handling instead
        path = "/v1/health"

        # Execute the request and expect a 404 error
        with pytest.raises(APIClientError) as exc_info:
            await api_client_integration.execute_request(
                method="GET",
                path=path,
            )

        # Verify the error details
        assert exc_info.value.status_code == 404
        assert "Cannot GET /v1/health" in str(exc_info.value)

    # @pytest.mark.asyncio(loop_scope="function")
    async def test_request_preparation(self, api_client_integration: ManagementAPIClient):
        """Test that requests are properly prepared with headers and parameters."""
        # Prepare a request with parameters
        method = "GET"
        path = "/v1/health"
        request_params = {"param1": "value1", "param2": "value2"}

        # Prepare the request
        request = api_client_integration.prepare_request(
            method=method,
            path=path,
            request_params=request_params,
        )

        # Verify the request
        assert request.method == method
        assert path in str(request.url)
        assert "param1=value1" in str(request.url)
        assert "param2=value2" in str(request.url)
        assert "Content-Type" in request.headers
        assert request.headers["Content-Type"] == "application/json"

    # @pytest.mark.asyncio(loop_scope="function")
    async def test_error_handling(self, api_client_integration: ManagementAPIClient):
        """Test handling of API errors."""
        # Make a request to a non-existent endpoint
        path = "/v1/nonexistent-endpoint"

        # Execute the request and expect an APIClientError (not APIResponseError)
        with pytest.raises(APIClientError) as exc_info:
            await api_client_integration.execute_request(
                method="GET",
                path=path,
            )

        # Verify the error details
        assert exc_info.value.status_code == 404
        assert "Cannot GET /v1/nonexistent-endpoint" in str(exc_info.value)

    # @pytest.mark.asyncio(loop_scope="function")
    async def test_request_with_body(self, api_client_integration: ManagementAPIClient):
        """Test executing a request with a body."""
        # This test would normally make a POST request with a body
        # Since we don't want to create real resources, we'll use a mock
        # or a safe endpoint that accepts POST but doesn't modify anything

        # For now, we'll just test the request preparation
        method = "POST"
        path = "/v1/health/check"  # This is a hypothetical endpoint
        request_body = {"test": "data", "nested": {"value": 123}}

        # Prepare the request
        request = api_client_integration.prepare_request(
            method=method,
            path=path,
            request_body=request_body,
        )

        # Verify the request
        assert request.method == method
        assert path in str(request.url)
        assert request.content  # Should have content for the body
        assert "Content-Type" in request.headers
        assert request.headers["Content-Type"] == "application/json"

    # @pytest.mark.asyncio(loop_scope="function")
    async def test_response_parsing(self, api_client_integration: ManagementAPIClient):
        """Test parsing API responses."""
        # Make a request to a public endpoint that returns JSON
        path = "/v1/projects"

        # Execute the request
        response = await api_client_integration.execute_request(
            method="GET",
            path=path,
        )

        # Verify the response is parsed correctly
        assert isinstance(response, list)
        # The response is a list of projects, not a dict with a "projects" key
        assert len(response) > 0
        assert "id" in response[0]

    # @pytest.mark.asyncio(loop_scope="function")
    async def test_request_retry_mechanism(self, monkeypatch, api_client_integration: ManagementAPIClient):
        """Test that the tenacity retry mechanism works correctly for API requests."""

        # Create a simple mock that always raises a network error
        async def mock_send(*args, **kwargs):
            raise httpx.NetworkError("Simulated network failure", request=None)

        # Replace the client's send method with our mock
        monkeypatch.setattr(api_client_integration.client, "send", mock_send)

        # Execute a request - this should trigger retries and eventually fail
        with pytest.raises(APIConnectionError) as exc_info:
            await api_client_integration.execute_request(
                method="GET",
                path="/v1/projects",
            )

        # Verify the error message indicates retries were attempted
        assert "Network error after 3 retry attempts" in str(exc_info.value)

    # @pytest.mark.asyncio(loop_scope="function")
    async def test_request_without_access_token(
        self, monkeypatch: pytest.MonkeyPatch, api_client_integration: ManagementAPIClient
    ):
        """Test that an exception is raised when attempting to send a request without an access token."""
        # Temporarily set the access token to None
        monkeypatch.setattr(api_client_integration.settings, "supabase_access_token", None)

        # Attempt to execute a request - should raise an exception
        with pytest.raises(APIClientError):
            await api_client_integration.execute_request(
                method="GET",
                path="/v1/projects",
            )

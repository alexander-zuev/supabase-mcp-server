from abc import ABC, abstractmethod
from json.decoder import JSONDecodeError
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel
from tenacity import RetryCallState, retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from supabase_mcp.exceptions import (
    APIClientError,
    APIConnectionError,
    APIResponseError,
    APIServerError,
    UnexpectedError,
)
from supabase_mcp.logger import logger

T = TypeVar("T")


# Helper function for retry decorator to safely log exceptions
def log_retry_attempt(retry_state: RetryCallState) -> None:
    """Log retry attempts with exception details if available."""
    exception = retry_state.outcome.exception() if retry_state.outcome and retry_state.outcome.failed else None
    exception_str = str(exception) if exception else "Unknown error"
    logger.warning(f"Network error, retrying ({retry_state.attempt_number}/3): {exception_str}")


class AsyncHTTPClient(ABC):
    """Abstract base class for async HTTP clients."""

    @abstractmethod
    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure client exists and is ready for use.

        Creates the client if it doesn't exist yet.
        Returns the client instance.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the client and release resources.

        Should be called when the client is no longer needed.
        """
        pass

    def prepare_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        request_params: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> httpx.Request:
        """
        Prepare an HTTP request.

        Args:
            client: The httpx client to use
            method: HTTP method (GET, POST, etc.)
            path: API path
            request_params: Query parameters
            request_body: Request body

        Returns:
            Prepared httpx.Request object

        Raises:
            APIClientError: If request preparation fails
        """
        try:
            return client.build_request(method=method, url=path, params=request_params, json=request_body)
        except Exception as e:
            raise APIClientError(
                message=f"Failed to build request: {str(e)}",
                status_code=None,
            ) from e

    @retry(
        retry=retry_if_exception_type(httpx.NetworkError),  # This includes ConnectError and TimeoutException
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,  # Ensure the original exception is raised
        before_sleep=log_retry_attempt,
    )
    async def send_request(self, client: httpx.AsyncClient, request: httpx.Request) -> httpx.Response:
        """
        Send an HTTP request with retry logic for transient errors.

        Args:
            client: The httpx client to use
            request: Prepared httpx.Request object

        Returns:
            httpx.Response object

        Raises:
            APIConnectionError: For connection issues
            APIClientError: For other request errors
        """
        try:
            return await client.send(request)
        except httpx.NetworkError as e:
            # All NetworkErrors will be retried by the decorator
            # This will only be reached after all retries are exhausted
            logger.error(f"Network error after all retry attempts: {str(e)}")
            raise APIConnectionError(
                message=f"Network error after 3 retry attempts: {str(e)}",
                status_code=None,
            ) from e
        except Exception as e:
            # Other exceptions won't be retried
            raise APIClientError(
                message=f"Request failed: {str(e)}",
                status_code=None,
            ) from e

    def parse_response(self, response: httpx.Response) -> dict[str, Any]:
        """
        Parse an HTTP response as JSON.

        Args:
            response: httpx.Response object

        Returns:
            Parsed response body as dictionary

        Raises:
            APIResponseError: If response cannot be parsed as JSON
        """
        if not response.content:
            return {}

        try:
            return response.json()
        except JSONDecodeError as e:
            raise APIResponseError(
                message=f"Failed to parse response as JSON: {str(e)}",
                status_code=response.status_code,
                response_body={"raw_content": response.text},
            ) from e

    def handle_error_response(self, response: httpx.Response, parsed_body: dict[str, Any] | None = None) -> None:
        """
        Handle error responses based on status code.

        Args:
            response: httpx.Response object
            parsed_body: Parsed response body if available

        Raises:
            APIClientError: For client errors (4xx)
            APIServerError: For server errors (5xx)
            UnexpectedError: For unexpected status codes
        """
        # Extract error message
        error_message = f"API request failed: {response.status_code}"
        if parsed_body and "message" in parsed_body:
            error_message = parsed_body["message"]

        # Determine error type based on status code
        if 400 <= response.status_code < 500:
            raise APIClientError(
                message=error_message,
                status_code=response.status_code,
                response_body=parsed_body,
            )
        elif response.status_code >= 500:
            raise APIServerError(
                message=error_message,
                status_code=response.status_code,
                response_body=parsed_body,
            )
        else:
            # This should not happen, but just in case
            raise UnexpectedError(
                message=f"Unexpected status code: {response.status_code}",
                status_code=response.status_code,
                response_body=parsed_body,
            )

    async def execute_request(
        self,
        method: str,
        path: str,
        request_params: dict[str, Any] | None = None,
        request_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | BaseModel:
        """
        Execute an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            request_params: Query parameters
            request_body: Request body

        Returns:
            API response as a dictionary

        Raises:
            APIClientError: For client errors (4xx)
            APIConnectionError: For connection issues
            APIResponseError: For response parsing errors
            UnexpectedError: For unexpected errors
        """
        # Log detailed request information
        logger.info(f"API Client: Executing {method} request to {path}")
        if request_params:
            logger.debug(f"Request params: {request_params}")
        if request_body:
            logger.debug(f"Request body: {request_body}")

        # Get client
        client = await self._ensure_client()

        # Prepare request
        request = self.prepare_request(client, method, path, request_params, request_body)

        # Send request
        response = await self.send_request(client, request)

        # Parse response (for both success and error cases)
        parsed_body = self.parse_response(response)

        # Check if successful
        if not response.is_success:
            logger.warning(f"Request failed: {method} {path} - Status {response.status_code}")
            self.handle_error_response(response, parsed_body)

        # Log success and return
        logger.info(f"Request successful: {method} {path} - Status {response.status_code}")
        return parsed_body

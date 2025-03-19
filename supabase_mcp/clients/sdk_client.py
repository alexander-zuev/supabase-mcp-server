from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from supabase import AsyncClient, create_async_client
from supabase.lib.client_options import AsyncClientOptions

from supabase_mcp.exceptions import PythonSDKError
from supabase_mcp.logger import logger
from supabase_mcp.services.sdk.auth_admin_models import (
    PARAM_MODELS,
    CreateUserParams,
    DeleteFactorParams,
    DeleteUserParams,
    GenerateLinkParams,
    GetUserByIdParams,
    InviteUserByEmailParams,
    ListUsersParams,
    UpdateUserByIdParams,
)
from supabase_mcp.services.sdk.auth_admin_sdk_spec import get_auth_admin_methods_spec
from supabase_mcp.settings import Settings

T = TypeVar("T", bound=BaseModel)


class IncorrectSDKParamsError(PythonSDKError):
    """Error raised when the parameters passed to the SDK are incorrect."""

    pass


class SupabaseSDKClient:
    """Supabase Python SDK client, which exposes functionality related to Auth admin of the Python SDK."""

    _instance: SupabaseSDKClient | None = None

    def __init__(
        self,
        settings: Settings | None = None,
        project_ref: str | None = None,
        service_role_key: str | None = None,
    ):
        self.client: AsyncClient | None = None
        self.settings = settings
        self.project_ref = settings.supabase_project_ref if settings else project_ref
        self.service_role_key = settings.supabase_service_role_key if settings else service_role_key
        self.supabase_url = self.get_supabase_url()
        logger.info(f"Initialized Supabase SDK client for project {self.project_ref}")

    def get_supabase_url(self) -> str:
        """Returns the Supabase URL based on the project reference"""
        if not self.project_ref:
            raise PythonSDKError("Project reference is not set")
        if self.project_ref.startswith("127.0.0.1"):
            # Return the default Supabase API URL
            return "http://127.0.0.1:54321"
        return f"https://{self.project_ref}.supabase.co"

    @classmethod
    def create(
        cls,
        settings: Settings | None = None,
        project_ref: str | None = None,
        service_role_key: str | None = None,
    ) -> SupabaseSDKClient:
        if cls._instance is None:
            cls._instance = cls(settings, project_ref, service_role_key)
        return cls._instance

    @classmethod
    def get_instance(
        cls,
        settings: Settings | None = None,
        project_ref: str | None = None,
        service_role_key: str | None = None,
    ) -> SupabaseSDKClient:
        """Returns the singleton instance"""
        if cls._instance is None:
            cls.create(settings, project_ref, service_role_key)
        return cls._instance

    async def create_client(self) -> AsyncClient:
        """Creates a new Supabase client"""
        try:
            client = await create_async_client(
                self.supabase_url,
                self.service_role_key,
                options=AsyncClientOptions(
                    auto_refresh_token=False,
                    persist_session=False,
                ),
            )
            return client
        except Exception as e:
            logger.error(f"Error creating Supabase client: {e}")
            raise PythonSDKError(f"Error creating Supabase client: {e}") from e

    async def get_client(self) -> AsyncClient:
        """Returns the Supabase client"""
        if not self.client:
            self.client = await self.create_client()
            logger.info(f"Created Supabase SDK client for project {self.project_ref}")
        return self.client

    async def close(self) -> None:
        """Reset the client reference to allow garbage collection."""
        self.client = None
        logger.info("Supabase SDK client reference cleared")

    def return_python_sdk_spec(self) -> dict:
        """Returns the Python SDK spec"""
        return get_auth_admin_methods_spec()

    def _validate_params(self, method: str, params: dict, param_model_cls: type[T]) -> T:
        """Validate parameters using the appropriate Pydantic model"""
        try:
            return param_model_cls.model_validate(params)
        except ValidationError as e:
            raise PythonSDKError(f"Invalid parameters for method {method}: {str(e)}") from e

    async def _get_user_by_id(self, params: GetUserByIdParams) -> dict:
        """Get user by ID implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin
        result = await admin_auth_client.get_user_by_id(params.uid)
        return result

    async def _list_users(self, params: ListUsersParams) -> dict:
        """List users implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin
        result = await admin_auth_client.list_users(page=params.page, per_page=params.per_page)
        return result

    async def _create_user(self, params: CreateUserParams) -> dict:
        """Create user implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin
        user_data = params.model_dump(exclude_none=True)
        result = await admin_auth_client.create_user(user_data)
        return result

    async def _delete_user(self, params: DeleteUserParams) -> dict:
        """Delete user implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin
        result = await admin_auth_client.delete_user(params.id, should_soft_delete=params.should_soft_delete)
        return result

    async def _invite_user_by_email(self, params: InviteUserByEmailParams) -> dict:
        """Invite user by email implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin
        options = params.options if params.options else {}
        result = await admin_auth_client.invite_user_by_email(params.email, options)
        return result

    async def _generate_link(self, params: GenerateLinkParams) -> dict:
        """Generate link implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin

        # Create a params dictionary as expected by the SDK
        params_dict = params.model_dump(exclude_none=True)

        try:
            # The SDK expects a single 'params' parameter containing all the fields
            result = await admin_auth_client.generate_link(params=params_dict)
            return result
        except TypeError as e:
            # Catch parameter errors and provide a more helpful message
            error_msg = str(e)
            if "unexpected keyword argument" in error_msg:
                raise IncorrectSDKParamsError(
                    f"Incorrect parameters for generate_link: {error_msg}. "
                    f"Please check the SDK specification for the correct parameter structure."
                ) from e
            raise

    async def _update_user_by_id(self, params: UpdateUserByIdParams) -> dict:
        """Update user by ID implementation"""
        self.client = await self.get_client()
        admin_auth_client = self.client.auth.admin
        uid = params.uid
        attributes = params.attributes.model_dump(exclude={"uid"}, exclude_none=True)
        result = await admin_auth_client.update_user_by_id(uid, attributes)
        return result

    async def _delete_factor(self, params: DeleteFactorParams) -> dict:
        """Delete factor implementation"""
        # This method is not implemented in the Supabase SDK yet
        raise NotImplementedError("The delete_factor method is not implemented in the Supabase SDK yet")

    async def call_auth_admin_method(self, method: str, params: dict[str, Any]) -> Any:
        """Calls a method of the Python SDK client"""
        # Check if service role key is available
        if not self.service_role_key:
            raise PythonSDKError(
                "Supabase service role key is not configured. Set SUPABASE_SERVICE_ROLE_KEY environment variable to use Auth Admin tools."
            )

        if not self.client:
            self.client = await self.get_client()
            if not self.client:
                raise PythonSDKError("Python SDK client not initialized")

        # Validate method exists
        if method not in PARAM_MODELS:
            available_methods = ", ".join(PARAM_MODELS.keys())
            raise PythonSDKError(f"Unknown method: {method}. Available methods: {available_methods}")

        # Get the appropriate model class and validate parameters
        param_model_cls = PARAM_MODELS[method]
        validated_params = self._validate_params(method, params, param_model_cls)

        # Method dispatch using a dictionary of method implementations
        method_handlers = {
            "get_user_by_id": self._get_user_by_id,
            "list_users": self._list_users,
            "create_user": self._create_user,
            "delete_user": self._delete_user,
            "invite_user_by_email": self._invite_user_by_email,
            "generate_link": self._generate_link,
            "update_user_by_id": self._update_user_by_id,
            "delete_factor": self._delete_factor,
        }

        # Call the appropriate method handler
        try:
            handler = method_handlers.get(method)
            if not handler:
                raise PythonSDKError(f"Method {method} is not implemented")

            logger.debug(f"Python SDK request params: {validated_params}")
            return await handler(validated_params)
        except Exception as e:
            if isinstance(e, IncorrectSDKParamsError):
                # Re-raise our custom error without wrapping it
                raise e
            logger.error(f"Error calling {method}: {e}")
            raise PythonSDKError(f"Error calling {method}: {str(e)}") from e

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance cleanly.

        This closes any open connections and resets the singleton instance.
        """
        if cls._instance is not None:
            cls._instance = None
            logger.info("SupabaseSDKClient instance reset complete")

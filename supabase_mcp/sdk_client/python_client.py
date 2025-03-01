from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from supabase import AsyncClient, create_async_client
from supabase.lib.client_options import ClientOptions

from supabase_mcp.exceptions import PythonSDKError
from supabase_mcp.logger import logger
from supabase_mcp.sdk_client.auth_admin_models import (
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
from supabase_mcp.sdk_client.auth_admin_sdk_spec import get_auth_admin_methods_spec
from supabase_mcp.settings import settings

T = TypeVar("T", bound=BaseModel)


class IncorrectSDKParamsError(PythonSDKError):
    """Error raised when the parameters passed to the SDK are incorrect."""

    pass


class SupabaseSDKClient:
    """Supabase Python SDK client, which exposes functionality related to Auth admin of the Python SDK."""

    _instance: SupabaseSDKClient | None = None

    def __init__(self, project_ref: str, service_role_key: str):
        self.client: AsyncClient | None = None
        self.project_ref = project_ref
        self.service_role_key = service_role_key

    def get_supabase_url(self) -> str:
        """Returns the Supabase URL based on the project reference"""
        if self.project_ref.startswith("127.0.0.1"):
            return "http://127.0.0.1:54321"
        return f"https://{self.project_ref}.supabase.co"

    @classmethod
    async def create(
        cls,
        project_ref: str = settings.supabase_project_ref,
        service_role_key: str = settings.supabase_service_role_key,
    ) -> SupabaseSDKClient:
        if cls._instance is None:
            try:
                cls._instance = cls(project_ref, service_role_key)
                supabase_url = cls._instance.get_supabase_url()
                cls._instance.client = await create_async_client(
                    supabase_url,
                    service_role_key,
                    options=ClientOptions(
                        auto_refresh_token=False,
                        persist_session=False,
                    ),
                )
                logger.info(f"Created Supabase SDK client for project {project_ref}")
            except Exception as e:
                logger.error(f"Error creating Supabase SDK client: {e}")
                raise PythonSDKError(f"Error creating Supabase SDK client: {e}") from e
        return cls._instance

    @classmethod
    async def get_instance(cls) -> SupabaseSDKClient:
        """Returns the singleton instance"""
        if cls._instance is None:
            await cls.create()
        return cls._instance

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
        admin_auth_client = self.client.auth.admin
        result = await admin_auth_client.get_user_by_id(params.uid)
        return result

    async def _list_users(self, params: ListUsersParams) -> dict:
        """List users implementation"""
        admin_auth_client = self.client.auth.admin
        result = await admin_auth_client.list_users(page=params.page, per_page=params.per_page)
        return result

    async def _create_user(self, params: CreateUserParams) -> dict:
        """Create user implementation"""
        admin_auth_client = self.client.auth.admin
        user_data = params.model_dump(exclude_none=True)
        result = await admin_auth_client.create_user(user_data)
        return result

    async def _delete_user(self, params: DeleteUserParams) -> dict:
        """Delete user implementation"""
        admin_auth_client = self.client.auth.admin
        result = await admin_auth_client.delete_user(params.id, should_soft_delete=params.should_soft_delete)
        return result

    async def _invite_user_by_email(self, params: InviteUserByEmailParams) -> dict:
        """Invite user by email implementation"""
        admin_auth_client = self.client.auth.admin
        options = params.options if params.options else {}
        result = await admin_auth_client.invite_user_by_email(params.email, options)
        return result

    async def _generate_link(self, params: GenerateLinkParams) -> dict:
        """Generate link implementation"""
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
        admin_auth_client = self.client.auth.admin
        uid = params.uid
        # Remove uid from attributes as it's passed separately
        attributes = params.model_dump(exclude={"uid"}, exclude_none=True)
        result = await admin_auth_client.update_user_by_id(uid, attributes)
        return result

    async def _delete_factor(self, params: DeleteFactorParams) -> dict:
        """Delete factor implementation"""
        # This method is not implemented in the Supabase SDK yet
        raise NotImplementedError("The delete_factor method is not implemented in the Supabase SDK yet")

    async def call_auth_admin_method(self, method: str, params: dict) -> Any:
        """Calls a method of the Python SDK client"""
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

            return await handler(validated_params)
        except Exception as e:
            if isinstance(e, IncorrectSDKParamsError):
                # Re-raise our custom error without wrapping it
                raise e
            logger.error(f"Error calling {method}: {e}")
            raise PythonSDKError(f"Error calling {method}: {str(e)}") from e

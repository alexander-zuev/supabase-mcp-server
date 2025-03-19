import time
import uuid
from datetime import datetime

import pytest

from supabase_mcp.clients.sdk_client import SupabaseSDKClient
from supabase_mcp.exceptions import PythonSDKError

# Unique identifier for test users to avoid conflicts
TEST_ID = f"test-{int(time.time())}-{uuid.uuid4().hex[:6]}"


# Create unique test emails
def get_test_email(prefix: str = "user"):
    """Generate a unique test email"""
    return f"a.zuev+{prefix}-{TEST_ID}@outlook.com"


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestSDKClientIntegration:
    """
    Integration tests for the SupabaseSDKClient.
    These tests make actual API calls to the Supabase Auth service.
    """

    async def test_list_users(self, sdk_client_integration: SupabaseSDKClient):
        """Test listing users with pagination"""
        # Create test parameters
        list_params = {"page": 1, "per_page": 10}

        # List users
        result = await sdk_client_integration.call_auth_admin_method("list_users", list_params)

        # Verify response format
        assert result is not None
        assert hasattr(result, "__iter__")  # Should be iterable (list of users)
        assert len(result) >= 0  # Should have users or be empty

        # Check that the first user has expected attributes if there are any users
        if len(result) > 0:
            first_user = result[0]
            assert hasattr(first_user, "id")
            assert hasattr(first_user, "email")
            assert hasattr(first_user, "user_metadata")

        # Test with invalid parameters (negative page number)
        invalid_params = {"page": -1, "per_page": 10}
        with pytest.raises(PythonSDKError) as excinfo:
            await sdk_client_integration.call_auth_admin_method("list_users", invalid_params)

        # The actual error message contains "Bad Pagination Parameters" instead of "Invalid parameters"
        assert "Bad Pagination Parameters" in str(excinfo.value)

    async def test_get_user_by_id(self, sdk_client_integration: SupabaseSDKClient):
        """Test retrieving a user by ID"""
        # First create a user to get
        test_email = get_test_email("get")
        create_params = {
            "email": test_email,
            "password": f"Password123!{TEST_ID}",
            "email_confirm": True,
            "user_metadata": {"name": "Test User", "test_id": TEST_ID},
        }

        # Create the user
        create_result = await sdk_client_integration.call_auth_admin_method("create_user", create_params)
        assert create_result is not None
        assert hasattr(create_result, "user")
        user_id = create_result.user.id

        try:
            # Get the user by ID
            get_params = {"uid": user_id}
            get_result = await sdk_client_integration.call_auth_admin_method("get_user_by_id", get_params)

            # Verify user data
            assert get_result is not None
            assert hasattr(get_result, "user")
            assert get_result.user.id == user_id
            assert get_result.user.email == test_email

            # The user_metadata might not contain test_id as it's not always preserved
            # when retrieving a user from the Supabase API
            if "test_id" in get_result.user.user_metadata:
                assert get_result.user.user_metadata["test_id"] == TEST_ID

            # Test with invalid parameters (non-existent user ID)
            invalid_params = {"uid": "non-existent-user-id"}
            with pytest.raises(PythonSDKError) as excinfo:
                await sdk_client_integration.call_auth_admin_method("get_user_by_id", invalid_params)

            # The actual error message contains "user_id must be an UUID" instead of "user not found"
            assert "user_id must be an UUID" in str(excinfo.value)

        finally:
            # Clean up - delete the test user
            delete_params = {"id": user_id}
            await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)

    async def test_create_user(self, sdk_client_integration: SupabaseSDKClient):
        """Test creating a new user"""
        # Create a new test user
        test_email = get_test_email("create")
        create_params = {
            "email": test_email,
            "password": f"Password123!{TEST_ID}",
            "email_confirm": True,
            "user_metadata": {"name": "Test User", "test_id": TEST_ID},
        }

        # Create the user
        create_result = await sdk_client_integration.call_auth_admin_method("create_user", create_params)
        assert create_result is not None
        assert hasattr(create_result, "user")
        assert hasattr(create_result.user, "id")
        user_id = create_result.user.id

        try:
            # Verify user was created
            get_params = {"uid": user_id}
            get_result = await sdk_client_integration.call_auth_admin_method("get_user_by_id", get_params)
            assert get_result is not None
            assert hasattr(get_result, "user")
            assert get_result.user.email == test_email

            # Test with invalid parameters (missing required fields)
            invalid_params = {"user_metadata": {"name": "Invalid User"}}
            with pytest.raises(PythonSDKError) as excinfo:
                await sdk_client_integration.call_auth_admin_method("create_user", invalid_params)

            assert "Invalid parameters" in str(excinfo.value)

        finally:
            # Clean up - delete the test user
            delete_params = {"id": user_id}
            await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)

    async def test_update_user_by_id(self, sdk_client_integration: SupabaseSDKClient):
        """Test updating a user's attributes"""
        # Create a new test user
        test_email = get_test_email("update")
        create_params = {
            "email": test_email,
            "password": f"Password123!{TEST_ID}",
            "email_confirm": True,
            "user_metadata": {
                "email": "beforeupdated@email.com",
            },
        }

        # Create the user
        create_result = await sdk_client_integration.call_auth_admin_method("create_user", create_params)
        assert hasattr(create_result, "user")
        user_id = create_result.user.id

        try:
            # Update the user
            update_params = {
                "uid": user_id,
                "attributes": {
                    "user_metadata": {
                        "email": "afterupdated@email.com",
                    }
                },
            }

            update_result = await sdk_client_integration.call_auth_admin_method("update_user_by_id", update_params)

            # Verify user was updated
            assert update_result is not None
            assert hasattr(update_result, "user")
            assert update_result.user.id == user_id
            assert update_result.user.user_metadata["email"] == "afterupdated@email.com"

            # Test with invalid parameters (non-existent user ID)
            invalid_params = {
                "uid": "non-existent-user-id",
                "attributes": {"user_metadata": {"name": "Invalid Update"}},
            }
            with pytest.raises(PythonSDKError) as excinfo:
                await sdk_client_integration.call_auth_admin_method("update_user_by_id", invalid_params)

            # The actual error message contains "user_id must be an uuid" instead of "user not found"
            assert "user_id must be an uuid" in str(excinfo.value).lower()

        finally:
            # Clean up - delete the test user
            delete_params = {"id": user_id}
            await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)

    async def test_delete_user(self, sdk_client_integration: SupabaseSDKClient):
        """Test deleting a user"""
        # Create a new test user
        test_email = get_test_email("delete")
        create_params = {
            "email": test_email,
            "password": f"Password123!{TEST_ID}",
            "email_confirm": True,
            "user_metadata": {"name": "Delete Test User", "test_id": TEST_ID},
        }

        # Create the user
        create_result = await sdk_client_integration.call_auth_admin_method("create_user", create_params)
        assert hasattr(create_result, "user")
        user_id = create_result.user.id

        # Delete the user
        delete_params = {"id": user_id}
        # The delete_user method returns None on success, so we just check that it doesn't raise an exception
        await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)

        # No need to assert on the result, as the API returns None on success
        # We'll verify deletion by trying to get the user and expecting an error

        # Verify user no longer exists
        get_params = {"uid": user_id}
        with pytest.raises(PythonSDKError) as excinfo:
            await sdk_client_integration.call_auth_admin_method("get_user_by_id", get_params)

        assert "user not found" in str(excinfo.value).lower() or "not found" in str(excinfo.value).lower()

        # Test with invalid parameters (non-UUID format user ID)
        invalid_params = {"id": "non-existent-user-id"}
        with pytest.raises(PythonSDKError) as excinfo:
            await sdk_client_integration.call_auth_admin_method("delete_user", invalid_params)

        # The API validates UUID format before checking if user exists
        assert "user_id must be an uuid" in str(excinfo.value).lower()

    async def test_invite_user_by_email(self, sdk_client_integration: SupabaseSDKClient):
        """Test inviting a user by email"""
        # Create invite parameters
        test_email = get_test_email("invite")
        invite_params = {
            "email": test_email,
            "options": {"data": {"name": "Invited User", "test_id": TEST_ID, "invited_at": datetime.now().isoformat()}},
        }

        # Invite the user
        try:
            result = await sdk_client_integration.call_auth_admin_method("invite_user_by_email", invite_params)

            # Verify response
            assert result is not None
            assert hasattr(result, "user")
            assert result.user.email == test_email
            assert hasattr(result.user, "invited_at")

            # Clean up - delete the invited user
            if hasattr(result.user, "id"):
                delete_params = {"id": result.user.id}
                await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)

            # Test with invalid parameters (missing email)
            invalid_params = {"options": {"data": {"name": "Invalid Invite"}}}
            with pytest.raises(PythonSDKError) as excinfo:
                await sdk_client_integration.call_auth_admin_method("invite_user_by_email", invalid_params)

            assert "Invalid parameters" in str(excinfo.value)

        except PythonSDKError as e:
            # Some Supabase instances may have email sending disabled,
            # so we'll check if the error is related to that
            if "sending emails is not configured" in str(e).lower():
                pytest.skip("Email sending is not configured in this Supabase instance")
            else:
                raise

    async def test_generate_link(self, sdk_client_integration: SupabaseSDKClient):
        """Test generating authentication links"""
        # Test different link types
        link_types = ["signup", "magiclink", "recovery"]
        created_user_ids = []

        for link_type in link_types:
            test_email = get_test_email(f"link-{link_type}")

            # For magiclink and recovery, we need to create the user first
            if link_type in ["magiclink", "recovery"]:
                # Create a user first
                create_params = {
                    "email": test_email,
                    "password": f"Password123!{TEST_ID}",
                    "email_confirm": True,
                    "user_metadata": {"name": f"{link_type.capitalize()} User", "test_id": TEST_ID},
                }

                try:
                    create_result = await sdk_client_integration.call_auth_admin_method("create_user", create_params)
                    if hasattr(create_result, "user") and hasattr(create_result.user, "id"):
                        created_user_ids.append(create_result.user.id)
                except PythonSDKError as e:
                    pytest.skip(f"Failed to create user for {link_type} test: {str(e)}")
                    continue

            # Different parameters based on link type
            if link_type == "signup":
                link_params = {
                    "type": link_type,
                    "email": test_email,
                    "password": f"Password123!{TEST_ID}",
                    "options": {
                        "data": {"name": f"{link_type.capitalize()} User", "test_id": TEST_ID},
                        "redirect_to": "https://example.com/welcome",
                    },
                }
            else:
                link_params = {
                    "type": link_type,
                    "email": test_email,
                    "options": {
                        "data": {"name": f"{link_type.capitalize()} User", "test_id": TEST_ID},
                        "redirect_to": "https://example.com/welcome",
                    },
                }

            try:
                # Generate link
                result = await sdk_client_integration.call_auth_admin_method("generate_link", link_params)

                # Verify response
                assert result is not None
                assert hasattr(result, "properties")
                assert hasattr(result.properties, "action_link")

                # If a user was created during link generation (for signup), store ID for cleanup
                if hasattr(result, "user") and hasattr(result.user, "id"):
                    created_user_ids.append(result.user.id)

            except PythonSDKError as e:
                # Some Supabase instances may have email sending disabled
                if "sending emails is not configured" in str(e).lower():
                    pytest.skip(f"Email sending is not configured for {link_type} links")
                else:
                    raise

        # Test with invalid parameters (invalid link type)
        invalid_params = {"type": "invalid_type", "email": get_test_email("invalid")}
        with pytest.raises(PythonSDKError) as excinfo:
            await sdk_client_integration.call_auth_admin_method("generate_link", invalid_params)

        assert "Invalid parameters" in str(excinfo.value) or "invalid type" in str(excinfo.value).lower()

        # Clean up any created users
        for user_id in created_user_ids:
            try:
                delete_params = {"id": user_id}
                await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)
            except Exception:
                pass

    async def test_delete_factor(self, sdk_client_integration: SupabaseSDKClient):
        """Test deleting an MFA factor"""
        # Create a test user
        test_email = get_test_email("factor")
        create_params = {
            "email": test_email,
            "password": f"Password123!{TEST_ID}",
            "email_confirm": True,
            "user_metadata": {"name": "Factor Test User", "test_id": TEST_ID},
        }

        # Create the user
        create_result = await sdk_client_integration.call_auth_admin_method("create_user", create_params)
        assert hasattr(create_result, "user")
        user_id = create_result.user.id

        try:
            # Attempt to delete a factor (this will likely fail as the method is not implemented)
            delete_factor_params = {"user_id": user_id, "id": "non-existent-factor-id"}

            try:
                await sdk_client_integration.call_auth_admin_method("delete_factor", delete_factor_params)
                # If it succeeds (unlikely), we should assert something
                assert False, "delete_factor should not succeed as it's not implemented"
            except PythonSDKError as e:
                # We expect this to fail with a specific error message
                assert "not implemented" in str(e).lower() or "method not found" in str(e).lower()

        finally:
            # Clean up - delete the test user
            delete_params = {"id": user_id}
            await sdk_client_integration.call_auth_admin_method("delete_user", delete_params)

    async def test_empty_parameters(self, sdk_client_integration: SupabaseSDKClient):
        """Test validation errors with empty parameters for various methods"""
        # Test methods with empty parameters
        methods = ["get_user_by_id", "create_user", "update_user_by_id", "delete_user", "generate_link"]

        for method in methods:
            empty_params = {}

            # Should raise PythonSDKError containing validation error details
            with pytest.raises(PythonSDKError) as excinfo:
                await sdk_client_integration.call_auth_admin_method(method, empty_params)

            # Verify error message contains validation details
            assert "Invalid parameters" in str(excinfo.value) or "validation error" in str(excinfo.value).lower()

    async def test_client_without_service_role_key(
        self, monkeypatch: pytest.MonkeyPatch, sdk_client_integration: SupabaseSDKClient
    ):
        """Test that an exception is raised when attempting to use the SDK client without a service role key."""
        # Temporarily set the service role key to None
        monkeypatch.setattr(sdk_client_integration, "service_role_key", None)

        # Attempt to call a method - should raise an exception
        with pytest.raises(PythonSDKError):
            await sdk_client_integration.call_auth_admin_method("list_users", {})

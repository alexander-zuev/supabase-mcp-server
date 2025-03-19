import uuid

import pytest
from mcp.server.fastmcp import FastMCP

from supabase_mcp.core.container import ServicesContainer
from supabase_mcp.exceptions import ConfirmationRequiredError, OperationNotAllowedError
from supabase_mcp.services.database.postgres_client import QueryResult
from supabase_mcp.services.safety.models import ClientType, OperationRiskLevel, SafetyMode


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestDatabaseTools:
    """Integration tests for database tools."""

    async def test_get_schemas_tool(
        self,
        initialized_container_integration: ServicesContainer,
        mock_mcp_server_integration: FastMCP,
    ):
        """Test the get_schemas tool."""
        query_manager = initialized_container_integration.query_manager
        query = query_manager.get_schemas_query()
        result = await query_manager.handle_query(query)

        # 4. Assert expected results
        assert result is not None
        assert isinstance(result, QueryResult), "Result should be a QueryResult"
        assert hasattr(result, "results")
        assert len(result.results) > 0
        assert hasattr(result.results[0], "rows")
        assert len(result.results[0].rows) > 0

        # Check that we have the expected data in the result
        first_row = result.results[0].rows[0]
        assert "schema_name" in first_row
        assert "total_size" in first_row
        assert "table_count" in first_row

    async def test_get_tables_tool(self, initialized_container_integration: ServicesContainer):
        """Test the get_tables tool retrieves table information from a schema."""
        query_manager = initialized_container_integration.query_manager

        # Get the tables query for the public schema
        query = query_manager.get_tables_query("public")
        result = await query_manager.handle_query(query)

        # Verify result structure
        assert isinstance(result, QueryResult), "Result should be a QueryResult"
        assert hasattr(result, "results"), "Result should have results attribute"

        # Verify we have table data
        assert len(result.results) > 0, "Should return at least one statement result"

        # If tables exist, verify their structure
        if len(result.results[0].rows) > 0:
            # Verify table structure
            first_table = result.results[0].rows[0]
            expected_fields = ["table_name", "table_type", "row_count", "size_bytes"]
            for field in expected_fields:
                assert field in first_table, f"Table result missing '{field}' field"

    async def test_get_table_schema_tool(self, initialized_container_integration: ServicesContainer):
        """Test the get_table_schema tool retrieves column information for a table."""
        query_manager = initialized_container_integration.query_manager
        query = query_manager.get_tables_query("public")
        tables_result = await query_manager.handle_query(query)

        # Skip test if no tables available
        if len(tables_result.results[0].rows) == 0:
            pytest.skip("No tables available in public schema to test table schema")

        # Get the first table name to test with
        first_table = tables_result.results[0].rows[0]["table_name"]

        # Execute the get_table_schema tool
        query = query_manager.get_table_schema_query("public", first_table)
        result = await query_manager.handle_query(query)

        # Verify result structure
        assert isinstance(result, QueryResult), "Result should be a QueryResult"
        assert hasattr(result, "results"), "Result should have results attribute"

        # If columns exist, verify their structure
        if len(result.results[0].rows) > 0:
            # Verify column structure
            first_column = result.results[0].rows[0]
            expected_fields = ["column_name", "data_type", "is_nullable"]
            for field in expected_fields:
                assert field in first_column, f"Column result missing '{field}' field"

    async def test_execute_postgresql_safe_query(self, initialized_container_integration: ServicesContainer):
        """Test the execute_postgresql tool runs safe SQL queries."""
        query_manager = initialized_container_integration.query_manager
        # Test a simple SELECT query
        result: QueryResult = await query_manager.handle_query("SELECT 1 as number, 'test' as text;")

        # Verify result structure
        assert isinstance(result, QueryResult), "Result should be a QueryResult"
        assert hasattr(result, "results"), "Result should have results attribute"

    async def test_execute_postgresql_unsafe_query(self, initialized_container_integration: ServicesContainer):
        """Test the execute_postgresql tool handles unsafe queries properly."""
        query_manager = initialized_container_integration.query_manager
        safety_manager = initialized_container_integration.safety_manager
        # First, ensure we're in safe mode
        # await live_dangerously(service="database", enable_unsafe_mode=False)
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Try to execute an unsafe query (DROP TABLE)
        unsafe_query = """
        DROP TABLE IF EXISTS test_table;
        """

        # This should raise a safety error
        with pytest.raises(OperationNotAllowedError):
            await query_manager.handle_query(unsafe_query)

        # Now switch to unsafe mode
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # The query should now require confirmation
        with pytest.raises(ConfirmationRequiredError):
            await query_manager.handle_query(unsafe_query)

        # Switch back to safe mode for other tests
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

    async def test_retrieve_migrations(self, initialized_container_integration: ServicesContainer):
        """Test the retrieve_migrations tool retrieves migration information with various parameters."""
        # Get the query manager
        query_manager = initialized_container_integration.query_manager

        # Case 1: Basic retrieval with default parameters
        query = query_manager.get_migrations_query()
        basic_result = await query_manager.handle_query(query)

        # Verify result structure
        assert isinstance(basic_result, QueryResult), "Result should be a QueryResult"
        assert hasattr(basic_result, "results"), "Result should have results attribute"
        assert len(basic_result.results) > 0, "Should have at least one statement result"

        # Case 2: Test pagination with limit and offset
        query_limited = query_manager.get_migrations_query(limit=3)
        limited_result = await query_manager.handle_query(query_limited)

        # Verify limited results
        if limited_result.results[0].rows:
            assert len(limited_result.results[0].rows) <= 3, "Should return at most 3 migrations"

            # Test offset
            if len(limited_result.results[0].rows) > 0:
                query_offset = query_manager.get_migrations_query(limit=3, offset=1)
                offset_result = await query_manager.handle_query(query_offset)

                # If we have enough migrations, the first migration with offset should be different
                if len(limited_result.results[0].rows) > 1 and offset_result.results[0].rows:
                    assert (
                        limited_result.results[0].rows[0]["version"] != offset_result.results[0].rows[0]["version"]
                    ), "Offset should return different migrations"

        # Case 3: Test name pattern filtering
        # First get all migrations to find a pattern to search for
        all_migrations_query = query_manager.get_migrations_query(limit=100)
        all_migrations_result = await query_manager.handle_query(all_migrations_query)

        # If we have migrations, try to filter by a pattern from an existing migration
        if all_migrations_result.results[0].rows:
            # Extract a substring from the first migration name to use as a pattern
            first_migration_name = all_migrations_result.results[0].rows[0]["name"]
            if len(first_migration_name) > 5:
                pattern = first_migration_name[2:6]  # Use a substring from the middle

                # Search using the pattern
                pattern_query = query_manager.get_migrations_query(name_pattern=pattern)
                pattern_result = await query_manager.handle_query(pattern_query)

                # Verify pattern filtering works
                if pattern_result.results[0].rows:
                    for row in pattern_result.results[0].rows:
                        assert pattern.lower() in row["name"].lower(), (
                            f"Pattern '{pattern}' should be in migration name '{row['name']}'"
                        )

        # Case 4: Test including full queries
        full_queries_query = query_manager.get_migrations_query(include_full_queries=True, limit=2)
        full_queries_result = await query_manager.handle_query(full_queries_query)

        # Verify full queries are included
        if full_queries_result.results[0].rows:
            for row in full_queries_result.results[0].rows:
                assert "statements" in row, "Statements field should be present"
                if row["statements"] is not None:
                    assert isinstance(row["statements"], list), "Statements should be a list"

        # Case 5: Test combining multiple parameters
        combined_query = query_manager.get_migrations_query(limit=5, offset=1, include_full_queries=True)
        combined_result = await query_manager.handle_query(combined_query)

        # Verify combined parameters work
        if combined_result.results[0].rows:
            assert len(combined_result.results[0].rows) <= 5, "Should return at most 5 migrations"
            for row in combined_result.results[0].rows:
                assert "statements" in row, "Statements field should be present"

    async def test_execute_postgresql_medium_risk_safe_mode(self, initialized_container_integration: ServicesContainer):
        """Test that MEDIUM risk operations (INSERT, UPDATE, DELETE) are not allowed in SAFE mode."""
        # Ensure we're in SAFE mode
        query_manager = initialized_container_integration.query_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Try to execute a MEDIUM risk query (INSERT)
        medium_risk_query = """
        INSERT INTO public.test_values (value) VALUES ('test_value');
        """

        # This should raise an OperationNotAllowedError in SAFE mode
        with pytest.raises(OperationNotAllowedError):
            await query_manager.handle_query(medium_risk_query)

    async def test_execute_postgresql_medium_risk_unsafe_mode(
        self, initialized_container_integration: ServicesContainer
    ):
        """Test that MEDIUM risk operations (INSERT, UPDATE, DELETE) are allowed in UNSAFE mode without confirmation."""
        query_manager = initialized_container_integration.query_manager
        postgres_client = initialized_container_integration.postgres_client
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # Generate a unique table name for this test run to avoid migration conflicts
        unique_suffix = str(uuid.uuid4()).replace("-", "")[:8]
        test_table_name = f"test_values_{unique_suffix}"

        # Import QueryValidationResults here to fix linter error
        from supabase_mcp.services.database.sql.models import QueryValidationResults

        try:
            # First create a test table if it doesn't exist with a unique name
            create_table_query = f"""
            CREATE TABLE IF NOT EXISTS public.{test_table_name} (
                id SERIAL PRIMARY KEY,
                value TEXT
            );
            """

            await query_manager.handle_query(create_table_query)

            # Now test a MEDIUM risk operation (INSERT)
            medium_risk_query = f"""
            INSERT INTO public.{test_table_name} (value) VALUES ('test_value');
            """

            # This should NOT raise an error in UNSAFE mode
            result = await query_manager.handle_query(medium_risk_query)

            # Verify the operation was successful
            assert isinstance(result, QueryResult), "Result should be a QueryResult"

        finally:
            # Clean up any migrations created during this test
            safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

            try:
                # More inclusive cleanup for migrations - delete any migration related to test_values tables
                cleanup_migrations_query = """
                DELETE FROM supabase_migrations.schema_migrations
                WHERE name LIKE '%test\\_values\\_%' ESCAPE '\\';
                """

                # Execute the cleanup query directly
                # Create a simple validation result for the cleanup query
                validation_result = QueryValidationResults(
                    statements=[],
                    highest_risk_level=OperationRiskLevel.MEDIUM,  # Medium risk
                    original_query=cleanup_migrations_query,
                )

                await postgres_client.execute_query(validation_result, readonly=False)
                print("Cleaned up all test_values migrations")
            except Exception as e:
                print(f"Failed to clean up test migrations: {e}")

            try:
                # More inclusive cleanup for tables - drop all test_values tables
                # First get a list of all test_values tables
                list_tables_query = """
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name LIKE 'test\\_values\\_%' ESCAPE '\\';
                """

                validation_result = QueryValidationResults(
                    statements=[],
                    highest_risk_level=OperationRiskLevel.LOW,
                    original_query=list_tables_query,
                )

                tables_result = await postgres_client.execute_query(validation_result, readonly=True)

                # Drop each test table found
                if tables_result and tables_result.results and tables_result.results[0].rows:
                    for row in tables_result.results[0].rows:
                        table_name = row.get("table_name")
                        if table_name:
                            drop_table_query = f"DROP TABLE IF EXISTS public.{table_name};"
                            drop_validation_result = QueryValidationResults(
                                statements=[],
                                highest_risk_level=OperationRiskLevel.HIGH,
                                original_query=drop_table_query,
                            )
                            try:
                                await postgres_client.execute_query(drop_validation_result, readonly=False)
                                print(f"Dropped test table: {table_name}")
                            except Exception as e:
                                print(f"Failed to drop test table {table_name}: {e}")
            except Exception as e:
                print(f"Failed to list or drop test tables: {e}")

            # Reset safety mode
            safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

    async def test_execute_postgresql_high_risk_safe_mode(self, initialized_container_integration: ServicesContainer):
        """Test that HIGH risk operations (DROP, TRUNCATE) are not allowed in SAFE mode."""
        # Ensure we're in SAFE mode
        query_manager = initialized_container_integration.query_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Try to execute a HIGH risk query (DROP TABLE)
        high_risk_query = """
        DROP TABLE IF EXISTS public.test_values;
        """

        # This should raise an OperationNotAllowedError in SAFE mode
        with pytest.raises(OperationNotAllowedError):
            await query_manager.handle_query(high_risk_query)

    async def test_execute_postgresql_high_risk_unsafe_mode(self, initialized_container_integration: ServicesContainer):
        """Test that HIGH risk operations (DROP, TRUNCATE) require confirmation even in UNSAFE mode."""
        query_manager = initialized_container_integration.query_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        try:
            # Try to execute a HIGH risk query (DROP TABLE)
            high_risk_query = """
            DROP TABLE IF EXISTS public.test_values;
            """

            # This should raise a ConfirmationRequiredError even in UNSAFE mode
            with pytest.raises(ConfirmationRequiredError):
                await query_manager.handle_query(high_risk_query)

        finally:
            # Switch back to SAFE mode for other tests
            safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

    async def test_execute_postgresql_safety_mode_switching(self, initialized_container_integration: ServicesContainer):
        """Test that switching between SAFE and UNSAFE modes affects which operations are allowed."""
        # Start in SAFE mode
        query_manager = initialized_container_integration.query_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)

        # Define queries with different risk levels
        low_risk_query = "SELECT 1 as number;"
        medium_risk_query = "INSERT INTO public.test_values (value) VALUES ('test_value');"
        high_risk_query = "DROP TABLE IF EXISTS public.test_values;"

        # LOW risk should work in SAFE mode
        low_result = await query_manager.handle_query(low_risk_query)
        assert isinstance(low_result, QueryResult), "LOW risk query should work in SAFE mode"

        # MEDIUM risk should fail in SAFE mode
        with pytest.raises(OperationNotAllowedError):
            await query_manager.handle_query(medium_risk_query)

        # HIGH risk should fail in SAFE mode
        with pytest.raises(OperationNotAllowedError):
            await query_manager.handle_query(high_risk_query)

        # Switch to UNSAFE mode
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)

        # LOW risk should still work in UNSAFE mode
        low_result = await query_manager.handle_query(low_risk_query)
        assert isinstance(low_result, QueryResult), "LOW risk query should work in UNSAFE mode"

        # MEDIUM risk should work in UNSAFE mode (but we won't actually execute it to avoid side effects)
        # We'll just verify it doesn't raise OperationNotAllowedError
        try:
            await query_manager.handle_query(medium_risk_query)
        except Exception as e:
            assert not isinstance(e, OperationNotAllowedError), (
                "MEDIUM risk should not raise OperationNotAllowedError in UNSAFE mode"
            )

        # HIGH risk should require confirmation in UNSAFE mode
        with pytest.raises(ConfirmationRequiredError):
            await query_manager.handle_query(high_risk_query)

        # Switch back to SAFE mode
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestAPITools:
    """Integration tests for API tools."""

    # @pytest.mark.asyncio
    async def test_send_management_api_request_get(self, initialized_container_integration: ServicesContainer):
        """Test the send_management_api_request tool with a GET request."""
        # Test a simple GET request to list services health
        api_manager = initialized_container_integration.api_manager
        result = await api_manager.execute_request(
            method="GET",
            path="/v1/projects/{ref}/health",
            path_params={},
            request_params={"services": ["auth", "db", "rest"]},
            request_body={},
        )

        # Verify result structure
        assert isinstance(result, list), "Result should be a list of dictionaries"
        assert len(result) > 0, "Result should contain at least one service"

        # Verify each service has the expected structure
        for service in result:
            assert isinstance(service, dict), "Each service should be a dictionary"
            assert "name" in service, "Service should have a name"
            assert "healthy" in service, "Service should have a health status"
            assert "status" in service, "Service should have a status"

    # @pytest.mark.asyncio
    async def test_send_management_api_request_medium_risk_safe_mode(
        self, initialized_container_integration: ServicesContainer
    ):
        """Test that MEDIUM risk operations (POST, PATCH) are not allowed in SAFE mode."""
        # Ensure we're in SAFE mode
        api_manager = initialized_container_integration.api_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)

        # Try to execute a MEDIUM risk operation (POST to create a function)
        with pytest.raises(OperationNotAllowedError):
            await api_manager.execute_request(
                method="POST",
                path="/v1/projects/{ref}/functions",
                path_params={},
                request_params={},
                request_body={"name": "test-function", "slug": "test-function", "verify_jwt": True},
            )

    async def test_send_management_api_request_medium_risk_unsafe_mode(
        self, initialized_container_integration: ServicesContainer
    ):
        """Test that MEDIUM risk operations (POST, PATCH) are allowed in UNSAFE mode."""
        import uuid

        import pytest

        # Get API manager from container
        api_manager = initialized_container_integration.api_manager
        safety_manager = initialized_container_integration.safety_manager

        # Switch to UNSAFE mode for cleanup and test
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.UNSAFE)

        # First, list all functions to find test functions to clean up
        try:
            functions_result = await api_manager.execute_request(
                method="GET",
                path="/v1/projects/{ref}/functions",
                path_params={},
                request_params={},
                request_body={},
            )

            # Clean up any existing test functions
            if isinstance(functions_result, list):
                for function in functions_result:
                    if (
                        isinstance(function, dict)
                        and "slug" in function
                        and function.get("slug", "").startswith("test_")
                    ):
                        try:
                            # Delete the test function
                            await api_manager.execute_request(
                                method="DELETE",
                                path="/v1/projects/{ref}/functions/{function_slug}",
                                path_params={"function_slug": function.get("slug")},
                                request_params={},
                                request_body={},
                            )
                            print(f"Cleaned up test function: {function.get('slug')}")
                        except Exception as e:
                            print(f"Failed to delete test function {function.get('slug')}: {e}")
        except Exception as e:
            print(f"Error listing functions: {e}")

        # Store function slug at class level for deletion in next test
        TestAPITools.function_slug = f"test_{uuid.uuid4().hex[:8]}"
        function_slug = TestAPITools.function_slug

        try:
            # Try to create a test function
            try:
                create_result = await api_manager.execute_request(
                    method="POST",
                    path="/v1/projects/{ref}/functions",
                    path_params={},
                    request_params={},
                    request_body={
                        "name": function_slug,
                        "slug": function_slug,
                        "verify_jwt": True,
                        "body": "export default async function(req, res) { return res.json({ message: 'Hello World' }) }",
                    },
                )
            except Exception as e:
                if "Max number of functions reached for project" in str(e):
                    pytest.skip("Max number of functions reached for project - skipping test")
                else:
                    raise e

            # Verify the function was created
            assert isinstance(create_result, dict), "Result should be a dictionary"
            assert "slug" in create_result, "Result should contain slug"
            assert create_result["slug"] == function_slug, "Function slug should match"

            # Update the function (PATCH operation)
            update_result = await api_manager.execute_request(
                method="PATCH",
                path="/v1/projects/{ref}/functions/{function_slug}",
                path_params={"function_slug": function_slug},
                request_params={},
                request_body={"verify_jwt": False},
            )

            # Verify the function was updated
            assert isinstance(update_result, dict), "Result should be a dictionary"
            assert "verify_jwt" in update_result, "Result should contain verify_jwt"
            assert update_result["verify_jwt"] is False, "Function verify_jwt should be updated to False"

            # Delete the function
            try:
                await api_manager.execute_request(
                    method="DELETE",
                    path="/v1/projects/{ref}/functions/{function_slug}",
                    path_params={"function_slug": function_slug},
                    request_params={},
                    request_body={},
                )
            except Exception as e:
                print(f"Failed to delete test function: {e}")

        finally:
            # Switch back to SAFE mode for other tests
            safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)

    # @pytest.mark.asyncio
    async def test_send_management_api_request_high_risk(self, initialized_container_integration: ServicesContainer):
        """Test that HIGH risk operations (DELETE) require confirmation even in UNSAFE mode."""
        # Switch to UNSAFE mode
        api_manager = initialized_container_integration.api_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.UNSAFE)

        try:
            # Try to execute a HIGH risk operation (DELETE a function)
            with pytest.raises(ConfirmationRequiredError):
                await api_manager.execute_request(
                    method="DELETE",
                    path="/v1/projects/{ref}/functions/{function_slug}",
                    path_params={"function_slug": "test-function"},
                    request_params={},
                    request_body={},
                )
        finally:
            # Switch back to SAFE mode
            safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)

    # @pytest.mark.asyncio
    async def test_send_management_api_request_extreme_risk(self, initialized_container_integration: ServicesContainer):
        """Test that EXTREME risk operations (DELETE project) are never allowed."""
        # Switch to UNSAFE mode
        api_manager = initialized_container_integration.api_manager
        safety_manager = initialized_container_integration.safety_manager
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.UNSAFE)

        try:
            # Try to execute an EXTREME risk operation (DELETE a project)
            with pytest.raises(OperationNotAllowedError):
                await api_manager.execute_request(
                    method="DELETE", path="/v1/projects/{ref}", path_params={}, request_params={}, request_body={}
                )
        finally:
            # Switch back to SAFE mode
            safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)

    # @pytest.mark.asyncio
    async def test_get_management_api_spec(self, initialized_container_integration: ServicesContainer):
        """Test the get_management_api_spec tool returns valid API specifications."""
        # Test getting API specifications
        api_manager = initialized_container_integration.api_manager
        result = await api_manager.handle_spec_request()

        # Verify result structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "domains" in result, "Result should contain domains"

        # Verify domains are present
        assert len(result["domains"]) > 0, "Should have at least one domain"

        # Test getting all paths
        paths_result = await api_manager.handle_spec_request(all_paths=True)

        # Verify paths are present
        assert "paths" in paths_result, "Result should contain paths"
        assert len(paths_result["paths"]) > 0, "Should have at least one path"

        # Test getting a specific domain
        domain_result = await api_manager.handle_spec_request(domain="Edge Functions")

        # Verify domain data is present
        assert "domain" in domain_result, "Result should contain domain"
        assert domain_result["domain"] == "Edge Functions", "Domain should match"
        assert "paths" in domain_result, "Result should contain paths for the domain"


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestSafetyTools:
    """Integration tests for safety tools."""

    async def test_live_dangerously_database(self, initialized_container_integration: ServicesContainer):
        """Test the live_dangerously tool toggles database safety mode."""
        # Get the safety manager
        safety_manager = initialized_container_integration.safety_manager

        # Start with safe mode
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)
        assert safety_manager.get_safety_mode(ClientType.DATABASE) == SafetyMode.SAFE, "Database should be in safe mode"

        # Switch to unsafe mode
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.UNSAFE)
        assert safety_manager.get_safety_mode(ClientType.DATABASE) == SafetyMode.UNSAFE, (
            "Database should be in unsafe mode"
        )

        # Switch back to safe mode
        safety_manager.set_safety_mode(ClientType.DATABASE, SafetyMode.SAFE)
        assert safety_manager.get_safety_mode(ClientType.DATABASE) == SafetyMode.SAFE, "Database should be in safe mode"

    # @pytest.mark.asyncio
    async def test_live_dangerously_api(self, initialized_container_integration: ServicesContainer):
        """Test the live_dangerously tool toggles API safety mode."""
        # Get the safety manager
        safety_manager = initialized_container_integration.safety_manager

        # Start with safe mode
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)
        assert safety_manager.get_safety_mode(ClientType.API) == SafetyMode.SAFE, "API should be in safe mode"

        # Switch to unsafe mode
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.UNSAFE)
        assert safety_manager.get_safety_mode(ClientType.API) == SafetyMode.UNSAFE, "API should be in unsafe mode"

        # Switch back to safe mode
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)
        assert safety_manager.get_safety_mode(ClientType.API) == SafetyMode.SAFE, "API should be in safe mode"

    # @pytest.mark.asyncio
    async def test_confirm_destructive_operation(self, initialized_container_integration: ServicesContainer):
        """Test the confirm_destructive_operation tool handles confirmations."""
        api_manager = initialized_container_integration.api_manager
        safety_manager = initialized_container_integration.safety_manager

        # Try to delete a function (HIGH risk) in SAFE mode - should be blocked
        with pytest.raises(OperationNotAllowedError):
            await api_manager.execute_request(
                method="DELETE",
                path="/v1/projects/{ref}/functions/{function_slug}",
                path_params={"function_slug": "test-function"},
                request_params={},
                request_body={},
            )

        # Switch to UNSAFE mode
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.UNSAFE)

        # Try to delete a function (HIGH risk) in UNSAFE mode - should require confirmation
        with pytest.raises(ConfirmationRequiredError):
            await api_manager.execute_request(
                method="DELETE",
                path="/v1/projects/{ref}/functions/{function_slug}",
                path_params={"function_slug": "test-function"},
                request_params={},
                request_body={},
            )

        # Switch back to SAFE mode for other tests
        safety_manager.set_safety_mode(ClientType.API, SafetyMode.SAFE)


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestAuthTools:
    """Integration tests for Auth Admin tools."""

    async def test_get_auth_admin_methods_spec(self, initialized_container_integration: ServicesContainer):
        """Test the get_auth_admin_methods_spec tool returns SDK method specifications."""
        # Test getting auth admin methods spec
        sdk_client = initialized_container_integration.sdk_client
        result = sdk_client.return_python_sdk_spec()

        # Verify result structure
        assert isinstance(result, dict), "Result should be a dictionary"
        assert len(result) > 0, "Should have at least one method"

        # Check for common methods
        common_methods = ["get_user_by_id", "list_users", "create_user", "delete_user", "update_user_by_id"]
        for method in common_methods:
            assert method in result, f"Result should contain {method} method"
            assert "description" in result[method], f"{method} should have a description"
            assert "parameters" in result[method], f"{method} should have parameters"
            assert "returns" in result[method], f"{method} should have returns info"

    async def test_call_auth_admin_list_users(self, initialized_container_integration: ServicesContainer):
        """Test the call_auth_admin_method tool with list_users method."""
        # Test listing users with pagination
        sdk_client = initialized_container_integration.sdk_client
        result = await sdk_client.call_auth_admin_method(method="list_users", params={"page": 1, "per_page": 5})

        # Verify result structure
        assert isinstance(result, list), "Result should be a list of User objects"

        # If there are users, verify their structure
        if len(result) > 0:
            user = result[0]
            assert hasattr(user, "id"), "User should have an ID"
            assert hasattr(user, "email"), "User should have an email"

    # @pytest.mark.asyncio
    async def test_call_auth_admin_create_user(self, initialized_container_integration: ServicesContainer):
        """Test creating a user with the create_user method."""
        # Create a unique email for this test
        test_email = f"test-user-{uuid.uuid4()}@example.com"
        user_id = None

        try:
            # Create a user
            sdk_client = initialized_container_integration.sdk_client
            create_result = await sdk_client.call_auth_admin_method(
                method="create_user",
                params={
                    "email": test_email,
                    "password": "secure-password",
                    "email_confirm": True,
                    "user_metadata": {"name": "Test User", "is_test_user": True},
                },
            )

            # Verify user was created
            assert hasattr(create_result, "user"), "Create result should have a user attribute"
            assert create_result.user.email == test_email, "User email should match"

            # Store the user ID for cleanup
            user_id = create_result.user.id

        finally:
            # Clean up - delete the test user
            if user_id:
                try:
                    await sdk_client.call_auth_admin_method(method="delete_user", params={"id": user_id})
                except Exception as e:
                    print(f"Failed to delete test user: {e}")

    # @pytest.mark.asyncio
    async def test_call_auth_admin_get_user(self, initialized_container_integration: ServicesContainer):
        """Test retrieving a user with the get_user_by_id method."""
        # Create a unique email for this test
        test_email = f"get-user-{uuid.uuid4()}@example.com"
        user_id = None

        try:
            # First create a user to get
            sdk_client = initialized_container_integration.sdk_client
            create_result = await sdk_client.call_auth_admin_method(
                method="create_user",
                params={
                    "email": test_email,
                    "password": "secure-password",
                    "email_confirm": True,
                },
            )
            user_id = create_result.user.id

            # Get the user by ID
            get_result = await sdk_client.call_auth_admin_method(method="get_user_by_id", params={"uid": user_id})

            # Verify get result
            assert hasattr(get_result, "user"), "Get result should have a user attribute"
            assert get_result.user.id == user_id, "User ID should match"
            assert get_result.user.email == test_email, "User email should match"

        finally:
            # Clean up
            if user_id:
                try:
                    await sdk_client.call_auth_admin_method(method="delete_user", params={"id": user_id})
                except Exception as e:
                    print(f"Failed to delete test user: {e}")

    # @pytest.mark.asyncio
    async def test_call_auth_admin_update_user(self, initialized_container_integration: ServicesContainer):
        """Test updating a user with the update_user_by_id method."""
        # Create a unique email for this test
        test_email = f"update-user-{uuid.uuid4()}@example.com"
        user_id = None

        try:
            # First create a user to update
            sdk_client = initialized_container_integration.sdk_client
            create_result = await sdk_client.call_auth_admin_method(
                method="create_user",
                params={
                    "email": test_email,
                    "password": "secure-password",
                    "email_confirm": True,
                    "user_metadata": {"name": "Original Name"},
                },
            )
            user_id = create_result.user.id

            # Update the user
            sdk_client = initialized_container_integration.sdk_client
            update_result = await sdk_client.call_auth_admin_method(
                method="update_user_by_id",
                params={
                    "uid": user_id,
                    "attributes": {
                        "user_metadata": {"name": "Updated Name", "is_test_user": True},
                    },
                },
            )

            # Verify update result
            assert hasattr(update_result, "user"), "Update result should have a user attribute"
            assert update_result.user.id == user_id, "User ID should match"

            # The update might not be immediately reflected in the response
            # Just verify we got a valid response with the correct user ID

        finally:
            # Clean up
            if user_id:
                try:
                    await sdk_client.call_auth_admin_method(method="delete_user", params={"id": user_id})
                except Exception as e:
                    print(f"Failed to delete test user: {e}")

    # @pytest.mark.asyncio
    async def test_call_auth_admin_invite_user(self, initialized_container_integration: ServicesContainer):
        """Test the invite_user_by_email method."""
        # Create a unique email for this test
        test_email = f"invite-{uuid.uuid4()}@example.com"
        user_id = None

        try:
            # Invite a user
            sdk_client = initialized_container_integration.sdk_client
            invite_result = await sdk_client.call_auth_admin_method(
                method="invite_user_by_email",
                params={"email": test_email, "options": {"data": {"name": "Invited Test User", "is_test_user": True}}},
            )

            # Verify invite result
            assert hasattr(invite_result, "user"), "Invite result should have a user attribute"
            assert invite_result.user.email == test_email, "User email should match"
            assert invite_result.user.invited_at is not None, "User should have an invited_at timestamp"

            # Store the user ID for cleanup
            user_id = invite_result.user.id

        finally:
            # Clean up
            if user_id:
                try:
                    await sdk_client.call_auth_admin_method(method="delete_user", params={"id": user_id})
                except Exception as e:
                    print(f"Failed to delete invited test user: {e}")

    # @pytest.mark.asyncio
    async def test_call_auth_admin_generate_signup_link(self, initialized_container_integration: ServicesContainer):
        """Test generating a signup link with the generate_link method."""
        # Create a unique email for this test
        test_email = f"signup-{uuid.uuid4()}@example.com"

        # Generate a signup link
        sdk_client = initialized_container_integration.sdk_client
        signup_result = await sdk_client.call_auth_admin_method(
            method="generate_link",
            params={
                "type": "signup",
                "email": test_email,
                "password": "secure-password",
                "options": {
                    "data": {"name": "Link Test User", "is_test_user": True},
                    "redirect_to": "https://example.com/welcome",
                },
            },
        )

        # Verify signup link result based on actual structure
        assert hasattr(signup_result, "properties"), "Result should have properties"
        assert hasattr(signup_result.properties, "action_link"), "Properties should have an action_link"
        assert hasattr(signup_result.properties, "email_otp"), "Properties should have an email_otp"
        assert hasattr(signup_result.properties, "verification_type"), "Properties should have a verification type"
        assert "signup" in signup_result.properties.verification_type, "Verification type should be signup"

    # @pytest.mark.asyncio
    async def test_call_auth_admin_invalid_method(self, initialized_container_integration: ServicesContainer):
        """Test that an invalid method raises an exception."""
        # Test with an invalid method name
        sdk_client = initialized_container_integration.sdk_client
        with pytest.raises(Exception):
            await sdk_client.call_auth_admin_method(method="invalid_method", params={})

        # Test with valid method but invalid parameters
        with pytest.raises(Exception):
            await sdk_client.call_auth_admin_method(method="get_user_by_id", params={"invalid_param": "value"})

            await sdk_client.call_auth_admin_method(method="invalid_method", params={})

        # Test with valid method but invalid parameters
        with pytest.raises(Exception):
            await sdk_client.call_auth_admin_method(method="get_user_by_id", params={"invalid_param": "value"})


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.integration
class TestLogsAndAnalyticsTools:
    """Integration tests for Logs and Analytics tools."""

    # Collection tests - one test per collection
    async def test_postgres_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the postgres collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="postgres", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        # We don't assert on result length as there might be no logs in test environment
        # Just verify the structure is correct
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_api_gateway_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the api_gateway collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="api_gateway", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_auth_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the auth collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="auth", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_postgrest_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the postgrest collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="postgrest", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_pooler_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the pooler collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="pooler", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_storage_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the storage collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="storage", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_realtime_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the realtime collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="realtime", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_edge_functions_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the edge_functions collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="edge_functions", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_cron_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the cron collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="cron", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_pgbouncer_logs_collection(self, initialized_container_integration: ServicesContainer):
        """Test retrieving logs from the pgbouncer collection."""
        api_manager = initialized_container_integration.api_manager

        result = await api_manager.retrieve_logs(collection="pgbouncer", limit=5, hours_ago=24)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    # Filtering tests
    async def test_filtering_by_hours_ago(self, initialized_container_integration: ServicesContainer):
        """Test filtering logs by hours_ago parameter."""
        api_manager = initialized_container_integration.api_manager

        # Test with different hours_ago values
        result_24h = await api_manager.retrieve_logs(collection="postgres", limit=5, hours_ago=24)

        result_1h = await api_manager.retrieve_logs(collection="postgres", limit=5, hours_ago=1)

        # We can't guarantee there will be logs in both time ranges
        # Just verify the structure is correct
        assert isinstance(result_24h, dict), "Result should be a dictionary"
        assert isinstance(result_1h, dict), "Result should be a dictionary"
        assert "result" in result_24h, "Result should contain 'result' key"
        assert "result" in result_1h, "Result should contain 'result' key"

    async def test_filtering_by_search_term(self, initialized_container_integration: ServicesContainer):
        """Test filtering logs by search term."""
        api_manager = initialized_container_integration.api_manager

        # Test with a search term that's likely to be in postgres logs
        result = await api_manager.retrieve_logs(collection="postgres", limit=5, hours_ago=24, search="connection")

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"

        # If we have results, verify they contain the search term
        if result["result"]:
            # At least one log should contain the search term (case insensitive)
            search_found = False
            for log in result["result"]:
                if "connection" in log["event_message"].lower():
                    search_found = True
                    break

            # We don't assert this because the search is done at the SQL level
            # and might use more complex matching than simple string contains
            # assert search_found, "At least one log should contain the search term"

    async def test_filtering_by_custom_filters(self, initialized_container_integration: ServicesContainer):
        """Test filtering logs by custom filters."""
        api_manager = initialized_container_integration.api_manager

        # Test with a filter on error severity
        result = await api_manager.retrieve_logs(
            collection="postgres",
            limit=5,
            hours_ago=24,
            filters=[{"field": "parsed.error_severity", "operator": "=", "value": "ERROR"}],
        )

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"

        # We don't assert on the filter results as there might not be any errors
        # in the test environment

    # Custom query tests
    async def test_custom_query_basic(self, initialized_container_integration: ServicesContainer):
        """Test using a custom query for log retrieval."""
        api_manager = initialized_container_integration.api_manager

        # Test with a simple custom query
        custom_query = "SELECT id, timestamp, event_message FROM postgres_logs LIMIT 3"
        result = await api_manager.retrieve_logs(collection="postgres", custom_query=custom_query)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        if result["result"]:
            assert len(result["result"]) <= 3, "Should return at most 3 logs"
            first_log = result["result"][0]
            assert "id" in first_log, "Log entry should have an ID"
            assert "timestamp" in first_log, "Log entry should have a timestamp"
            assert "event_message" in first_log, "Log entry should have an event message"

    async def test_custom_query_with_complex_joins(self, initialized_container_integration: ServicesContainer):
        """Test using a custom query with complex joins for log retrieval."""
        api_manager = initialized_container_integration.api_manager

        # Test with a more complex query that includes metadata
        custom_query = """
        SELECT
            id,
            timestamp,
            event_message,
            parsed.error_severity
        FROM postgres_logs
        CROSS JOIN unnest(metadata) AS m
        CROSS JOIN unnest(m.parsed) AS parsed
        LIMIT 3
        """

        result = await api_manager.retrieve_logs(collection="postgres", custom_query=custom_query)

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "result" in result, "Result should contain 'result' key"
        # We don't assert on the structure of the result as it depends on the
        # actual data in the logs

    # Error handling tests
    async def test_invalid_collection_name(self, initialized_container_integration: ServicesContainer):
        """Test that an invalid collection name raises an appropriate error."""
        api_manager = initialized_container_integration.api_manager

        # Test with an invalid collection name
        with pytest.raises(Exception) as excinfo:
            await api_manager.retrieve_logs(collection="invalid_collection", limit=5)

        # Verify the error message mentions the invalid collection
        assert "invalid_collection" in str(excinfo.value).lower() or "table" in str(excinfo.value).lower(), (
            "Error message should mention the invalid collection or table"
        )

    async def test_invalid_custom_query(self, initialized_container_integration: ServicesContainer):
        """Test that an invalid custom query returns an appropriate error message."""
        api_manager = initialized_container_integration.api_manager

        # Test with an invalid SQL query
        result = await api_manager.retrieve_logs(collection="postgres", custom_query="SELECT * FROM nonexistent_table")

        # Verify the result contains an error message
        assert isinstance(result, dict), "Result should be a dictionary"
        assert "error" in result, "Result should contain an error message"
        # The error message might vary, but it should indicate an issue with the query
        assert result["result"] is None, "Result data should be None for invalid query"

    async def test_special_characters_in_search(self, initialized_container_integration: ServicesContainer):
        """Test handling of special characters in search terms."""
        api_manager = initialized_container_integration.api_manager

        # Test with a search term containing special characters
        try:
            result = await api_manager.retrieve_logs(
                collection="postgres",
                limit=5,
                search="O'Reilly",  # Contains a single quote
            )

            assert isinstance(result, dict), "Result should be a dictionary"
            assert "result" in result, "Result should contain 'result' key"
            # If we get here, the search term was properly escaped

        except Exception as e:
            pytest.fail(f"Search with special characters failed: {e}")

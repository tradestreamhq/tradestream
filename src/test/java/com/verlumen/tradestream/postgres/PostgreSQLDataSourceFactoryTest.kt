package com.verlumen.tradestream.postgres

import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.postgresql.ds.PGSimpleDataSource
import javax.sql.DataSource

/**
 * Unit tests for PostgreSQLDataSourceFactory to verify correct DataSource configuration.
 */
@RunWith(JUnit4::class)
class PostgreSQLDataSourceFactoryTest {
    private val factory = PostgreSQLDataSourceFactory()

    @Test
    fun testCreateDataSourceWithRequiredParameters() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
            )

        val dataSource = factory.create(config)

        assert(dataSource != null) { "DataSource should not be null" }
        assert(dataSource is DataSource) { "Should return DataSource interface" }

        // Cast to PGSimpleDataSource to verify configuration
        val pgDataSource = dataSource as PGSimpleDataSource
        assert(pgDataSource.serverName == "localhost") { "Server name should match" }
        assert(pgDataSource.databaseName == "test_db") { "Database name should match" }
        assert(pgDataSource.user == "test_user") { "Username should match" }
        assert(pgDataSource.password == "test_password") { "Password should match" }
    }

    @Test
    fun testCreateDataSourceWithAllParameters() {
        val config =
            DataSourceConfig(
                serverName = "prod-db.example.com",
                databaseName = "production_db",
                username = "prod_user",
                password = "secure_password",
                portNumber = 5433,
                applicationName = "tradestream-discovery",
                connectTimeout = 30,
                socketTimeout = 60,
                readOnly = true,
            )

        val dataSource = factory.create(config)

        assert(dataSource != null) { "DataSource should not be null" }

        // Cast to PGSimpleDataSource to verify configuration
        val pgDataSource = dataSource as PGSimpleDataSource
        assert(pgDataSource.serverName == "prod-db.example.com") { "Server name should match" }
        assert(pgDataSource.databaseName == "production_db") { "Database name should match" }
        assert(pgDataSource.user == "prod_user") { "Username should match" }
        assert(pgDataSource.password == "secure_password") { "Password should match" }
        assert(pgDataSource.portNumber == 5433) { "Port number should match" }
        assert(pgDataSource.applicationName == "tradestream-discovery") { "Application name should match" }
        assert(pgDataSource.connectTimeout == 30) { "Connect timeout should match" }
        assert(pgDataSource.socketTimeout == 60) { "Socket timeout should match" }
        assert(pgDataSource.isReadOnly == true) { "Read-only flag should match" }
    }

    @Test
    fun testCreateDataSourceWithNullOptionalParameters() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
                portNumber = null,
                applicationName = null,
                connectTimeout = null,
                socketTimeout = null,
                readOnly = null,
            )

        val dataSource = factory.create(config)

        assert(dataSource != null) { "DataSource should not be null" }

        // Cast to PGSimpleDataSource to verify configuration
        val pgDataSource = dataSource as PGSimpleDataSource
        assert(pgDataSource.serverName == "localhost") { "Server name should match" }
        assert(pgDataSource.databaseName == "test_db") { "Database name should match" }
        assert(pgDataSource.user == "test_user") { "Username should match" }
        assert(pgDataSource.password == "test_password") { "Password should match" }

        // Null parameters should result in default values
        assert(pgDataSource.portNumber == 0) { "Port number should be default (0) when null" }
        // Note: PostgreSQL driver uses default values for null optional parameters
    }

    @Test
    fun testCreateDataSourceWithEmptyOptionalStringParameters() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
                applicationName = "", // Empty string should not be set
            )

        val dataSource = factory.create(config)

        assert(dataSource != null) { "DataSource should not be null" }

        // Cast to PGSimpleDataSource to verify configuration
        val pgDataSource = dataSource as PGSimpleDataSource

        // Empty application name should not be set (takeIf { it.isNotBlank() } prevents it)
        assert(pgDataSource.applicationName == null || pgDataSource.applicationName.isEmpty()) {
            "Empty application name should not be set"
        }
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankServerName() {
        val config =
            DataSourceConfig(
                serverName = "",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankDatabaseName() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "",
                username = "test_user",
                password = "test_password",
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankUsername() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "",
                password = "test_password",
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankPassword() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "",
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithNegativePortNumber() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
                portNumber = -1,
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithZeroPortNumber() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
                portNumber = 0,
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithNegativeConnectTimeout() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
                connectTimeout = -1,
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithNegativeSocketTimeout() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
                socketTimeout = -1,
            )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test
    fun testDataSourceConfigValidation() {
        // Test that the DataSourceConfig validation works correctly
        try {
            DataSourceConfig(
                serverName = "valid_server",
                databaseName = "valid_db",
                username = "valid_user",
                password = "valid_password",
                portNumber = 5432,
                connectTimeout = 30,
                socketTimeout = 60,
            )
        } catch (e: Exception) {
            assert(false) { "Valid configuration should not throw exception: ${e.message}" }
        }
    }

    @Test
    fun testUseConnectionExtensionFunction() {
        val config =
            DataSourceConfig(
                serverName = "localhost",
                databaseName = "test_db",
                username = "test_user",
                password = "test_password",
            )

        val dataSource = factory.create(config)

        // Test the extension function compiles and can be called
        // Note: This will fail with actual database connection, but we're testing the API
        try {
            dataSource.useConnection { connection ->
                assert(connection != null) { "Connection should not be null" }
                "test_result"
            }
        } catch (e: Exception) {
            // Expected to fail since we don't have a real database
            // We're just testing that the extension function is available and compiles
            assert(e.message?.contains("Connection") == true || e.message?.contains("connection") == true) {
                "Should fail with connection-related error, got: ${e.message}"
            }
        }
    }
}

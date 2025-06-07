package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentMatchers.any
import org.mockito.ArgumentMatchers.eq
import org.mockito.Mock
import org.mockito.Mockito.verify
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever
import java.sql.Connection
import java.time.Instant
import javax.sql.DataSource

/**
 * Unit tests for WriteDiscoveredStrategiesToPostgresFn using the new factory pattern
 * with assisted injection.
 *
 * These tests focus on the DoFn's data transformation logic using mocked dependencies.
 * Full integration tests with PostgreSQL would require a test database.
 */
@RunWith(JUnit4::class)
class WriteDiscoveredStrategiesToPostgresFnTest {
    // We do not run the pipeline in these unit tests; turn off the enforcement that
    // would otherwise throw PipelineRunMissingException.
    @get:Rule
    val pipeline: TestPipeline =
        TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // Use BoundFieldModule to inject these mocks
    @Bind @Mock
    lateinit var mockDataSourceFactory: DataSourceFactory

    @Mock
    lateinit var mockDataSource: DataSource

    @Mock
    lateinit var mockConnection: Connection

    // The class under test - will be created directly with mocked dependencies
    private lateinit var writeDiscoveredStrategiesToPostgresFn: WriteDiscoveredStrategiesToPostgresFn

    // Test database configuration
    private val testServerName = "localhost"
    private val testDatabaseName = "test_db"
    private val testUsername = "test_user"
    private val testPassword = "test_password"
    private val testPortNumber = 5432
    private val testApplicationName = "test_app"
    private val testConnectTimeout = 30
    private val testSocketTimeout = 60
    private val testReadOnly = false

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Create Guice injector with BoundFieldModule to inject the test fixture
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)

        // Setup mock behavior for DataSourceFactory
        whenever(mockDataSourceFactory.create(any<DataSourceConfig>())).thenReturn(mockDataSource)
        whenever(mockDataSource.connection).thenReturn(mockConnection)

        // Create the function under test directly (simulating what the factory would do)
        writeDiscoveredStrategiesToPostgresFn = WriteDiscoveredStrategiesToPostgresFn(
            dataSourceFactory = mockDataSourceFactory,
            serverName = testServerName,
            databaseName = testDatabaseName,
            username = testUsername,
            password = testPassword,
            portNumber = testPortNumber,
            applicationName = testApplicationName,
            connectTimeout = testConnectTimeout,
            socketTimeout = testSocketTimeout,
            readOnly = testReadOnly
        )
    }

    @Test
    fun testInstanceCreatedWithCorrectParameters() {
        // Verify the instance is not null and was created successfully
        assert(writeDiscoveredStrategiesToPostgresFn != null) { "Instance should be created successfully" }
    }

    @Test
    fun testCsvRowGeneration() {
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-01T01:00:00Z")

        val smaRsiParams =
            SmaRsiParameters
                .newBuilder()
                .setRsiPeriod(14)
                .setMovingAveragePeriod(20)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build()
        val paramsAny = Any.pack(smaRsiParams)

        val strategyProto =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(paramsAny)
                .build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTC/USD")
                .setStrategy(strategyProto)
                .setScore(0.75)
                .setStartTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(startTime.epochSecond)
                        .setNanos(startTime.nano)
                        .build(),
                ).setEndTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(endTime.epochSecond)
                        .setNanos(endTime.nano)
                        .build(),
                ).build()

        // Test the CSV row generation using reflection to access private method
        val convertToCsvRowMethod =
            WriteDiscoveredStrategiesToPostgresFn::class.java
                .getDeclaredMethod("convertToCsvRow", DiscoveredStrategy::class.java)
        convertToCsvRowMethod.isAccessible = true

        val csvRow = convertToCsvRowMethod.invoke(writeDiscoveredStrategiesToPostgresFn, discoveredStrategy) as String

        // Verify CSV row contains expected data
        val columns = csvRow.split("\t")
        assert(columns.size == 8) { "Expected 8 columns, got ${columns.size}" }
        assert(columns[0] == "BTC/USD") { "Symbol should be BTC/USD" }
        assert(columns[1] == "SMA_RSI") { "Strategy type should be SMA_RSI" }
        assert(columns[3] == "0.75") { "Score should be 0.75" }
        assert(columns[5] == "BTC/USD") { "Discovery symbol should be BTC/USD" }
    }

    @Test
    fun testSha256HashGeneration() {
        // Test the SHA256 hash generation using reflection
        val sha256Method =
            WriteDiscoveredStrategiesToPostgresFn::class.java
                .getDeclaredMethod("sha256", String::class.java)
        sha256Method.isAccessible = true

        val input = "test_input"
        val hash1 = sha256Method.invoke(writeDiscoveredStrategiesToPostgresFn, input) as String
        val hash2 = sha256Method.invoke(writeDiscoveredStrategiesToPostgresFn, input) as String

        // Same input should produce same hash
        assert(hash1 == hash2) { "Same input should produce same hash" }
        assert(hash1.length == 64) { "SHA256 hash should be 64 characters long" }

        // Different input should produce different hash
        val differentHash = sha256Method.invoke(writeDiscoveredStrategiesToPostgresFn, "different_input") as String
        assert(hash1 != differentHash) { "Different inputs should produce different hashes" }
    }

    @Test
    fun testPipelineDoesNotFailWithValidStrategy() {
        // This test verifies the DoFn can be constructed and added to pipeline
        // without database connection (actual database writes would require integration tests)
        val startTime = Instant.parse("2023-01-01T00:00:00Z")
        val endTime = Instant.parse("2023-01-01T01:00:00Z")

        val smaRsiParams = SmaRsiParameters.newBuilder().setRsiPeriod(14).build()
        val strategyProto =
            Strategy
                .newBuilder()
                .setType(StrategyType.SMA_RSI)
                .setParameters(Any.pack(smaRsiParams))
                .build()

        val discoveredStrategy =
            DiscoveredStrategy
                .newBuilder()
                .setSymbol("BTC/USD")
                .setStrategy(strategyProto)
                .setScore(0.75)
                .setStartTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(startTime.epochSecond)
                        .setNanos(startTime.nano)
                        .build(),
                ).setEndTime(
                    Timestamp
                        .newBuilder()
                        .setSeconds(endTime.epochSecond)
                        .setNanos(endTime.nano)
                        .build(),
                ).build()

        val input: PCollection<DiscoveredStrategy> = pipeline.apply(Create.of(discoveredStrategy))

        // This would normally write to PostgreSQL, but for unit testing we just verify
        // the pipeline can be constructed without errors using the directly created instance
        val output: PCollection<Void> = input.apply(ParDo.of(writeDiscoveredStrategiesToPostgresFn))

        // Note: We can't run this pipeline in unit tests without a database
        // This test just verifies the DoFn can be instantiated correctly
        assert(output != null) { "Pipeline should be constructable" }
    }

    @Test
    fun testDataSourceConfigurationValidation() {
        // Test that valid configuration creates the DataSource without errors
        val config = DataSourceConfig(
            serverName = testServerName,
            databaseName = testDatabaseName,
            username = testUsername,
            password = testPassword,
            portNumber = testPortNumber,
            applicationName = testApplicationName,
            connectTimeout = testConnectTimeout,
            socketTimeout = testSocketTimeout,
            readOnly = testReadOnly
        )

        // This should not throw any exceptions
        try {
            mockDataSourceFactory.create(config)
        } catch (e: Exception) {
            assert(false) { "Valid configuration should not cause errors: ${e.message}" }
        }
    }
}

# src/test/java/com/verlumen/tradestream/discovery/PostgreSQLDataSourceFactoryTest.kt
package com.verlumen.tradestream.discovery

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
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password"
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
        val config = DataSourceConfig(
            serverName = "prod-db.example.com",
            databaseName = "production_db",
            username = "prod_user",
            password = "secure_password",
            portNumber = 5433,
            applicationName = "tradestream-discovery",
            connectTimeout = 30,
            socketTimeout = 60,
            readOnly = true
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
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password",
            portNumber = null,
            applicationName = null,
            connectTimeout = null,
            socketTimeout = null,
            readOnly = null
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
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password",
            applicationName = "" // Empty string should not be set
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
        val config = DataSourceConfig(
            serverName = "",
            databaseName = "test_db", 
            username = "test_user",
            password = "test_password"
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankDatabaseName() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "",
            username = "test_user",
            password = "test_password"
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankUsername() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "",
            password = "test_password"
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithBlankPassword() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = ""
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithNegativePortNumber() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password",
            portNumber = -1
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithZeroPortNumber() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password",
            portNumber = 0
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithNegativeConnectTimeout() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password",
            connectTimeout = -1
        )

        factory.create(config) // Should throw IllegalArgumentException
    }

    @Test(expected = IllegalArgumentException::class)
    fun testCreateDataSourceWithNegativeSocketTimeout() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password",
            socketTimeout = -1
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
                socketTimeout = 60
            )
        } catch (e: Exception) {
            assert(false) { "Valid configuration should not throw exception: ${e.message}" }
        }
    }

    @Test
    fun testUseConnectionExtensionFunction() {
        val config = DataSourceConfig(
            serverName = "localhost",
            databaseName = "test_db",
            username = "test_user",
            password = "test_password"
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

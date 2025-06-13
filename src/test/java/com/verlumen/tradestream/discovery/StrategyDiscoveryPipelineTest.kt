package com.verlumen.tradestream.discovery

import com.google.common.truth.Truth.assertThat
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.sql.DataSourceConfig
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TypeDescriptors
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.ArgumentCaptor
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.times
import org.mockito.kotlin.verify
import org.mockito.kotlin.verifyNoMoreInteractions
import org.mockito.kotlin.whenever

/**
 * Comprehensive unit test suite for StrategyDiscoveryPipeline using Mockito and BoundFieldModule.
 *
 * Tests the pipeline construction, configuration, transform wiring, and execution logic
 * without actually running the Apache Beam pipeline.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineTest {
    @get:Rule
    val testPipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(false)

    // Mock all dependencies using BoundFieldModule
    @Bind @Mock
    lateinit var mockRunGAFn: RunGADiscoveryFn

    @Bind @Mock
    lateinit var mockExtractFn: ExtractDiscoveredStrategiesFn

    @Bind @Mock
    lateinit var mockWriteFnFactory: WriteDiscoveredStrategiesToPostgresFnFactory

    @Bind @Mock
    lateinit var mockDiscoveryRequestSourceFactory: DiscoveryRequestSourceFactory

    // Additional mocks for testing
    @Mock
    lateinit var mockWriteFn: WriteDiscoveredStrategiesToPostgresFn

    private lateinit var options: StrategyDiscoveryPipelineOptions

    // The class under test - injected by Guice
    @Inject
    lateinit var strategyDiscoveryPipeline: StrategyDiscoveryPipeline

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        options = testPipeline.options.`as`(StrategyDiscoveryPipelineOptions::class.java)

        // Create Guice injector with BoundFieldModule to inject mocked dependencies
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)

        // Setup default mock behaviors
        setupDefaultMockBehaviors()
    }

    private fun setupDefaultMockBehaviors() {
        // Configure options with valid database configuration
        options.databaseUsername = "test_user"
        options.databasePassword = "test_password"
        options.dbServerName = "localhost"
        options.dbDatabaseName = "test_db"
        options.dbPortNumber = 5432

        // Mock factory returns
        whenever(mockDiscoveryRequestSourceFactory.create(any())).thenReturn(
            object : DiscoveryRequestSource() {
                override fun expand(input: PBegin): PCollection<StrategyDiscoveryRequest> {
                    return input.pipeline.apply(
                        Create.empty(TypeDescriptors.of(StrategyDiscoveryRequest::class.java)),
                    )
                }
            },
        )
        whenever(mockWriteFnFactory.create(any())).thenReturn(mockWriteFn)
    }

    @Test
    fun testPipelineInstantiation() {
        // Verify that Guice can create an instance of StrategyDiscoveryPipeline
        assertThat(strategyDiscoveryPipeline).isNotNull()
    }

    @Test
    fun testValidOptionsProcessing() {
        // Test that valid options are processed correctly
        strategyDiscoveryPipeline.run(options)

        // Verify that factories were called with correct parameters
        verify(mockDiscoveryRequestSourceFactory).create(options)

        // Verify DataSourceConfig was created with correct parameters
        val dataSourceConfigCaptor = ArgumentCaptor.forClass(DataSourceConfig::class.java)
        verify(mockWriteFnFactory).create(dataSourceConfigCaptor.capture())

        val capturedConfig = dataSourceConfigCaptor.value
        assertThat(capturedConfig.serverName).isEqualTo("localhost")
        assertThat(capturedConfig.databaseName).isEqualTo("test_db")
        assertThat(capturedConfig.username).isEqualTo("test_user")
        assertThat(capturedConfig.password).isEqualTo("test_password")
        assertThat(capturedConfig.portNumber).isEqualTo(5432)
    }

    @Test
    fun testNullDatabaseUsernameThrowsException() {
        // Setup options with null username
        options.databaseUsername = null

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(options)
            fail("Should throw exception when database username is null")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testNullDatabasePasswordThrowsException() {
        // Setup options with null password
        options.databasePassword = null

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(options)
            fail("Should throw exception when database password is null")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testEmptyDatabaseUsernameThrowsException() {
        // Setup options with empty username
        options.databaseUsername = ""

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(options)
            fail("Should throw exception when database username is empty")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testEmptyDatabasePasswordThrowsException() {
        // Setup options with empty password
        options.databasePassword = ""

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(options)
            fail("Should throw exception when database password is empty")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testDataSourceConfigurationCreation() {
        // Setup options with all configuration values
        options.dbServerName = "custom-host"
        options.dbDatabaseName = "custom-db"
        options.databaseUsername = "custom-user"
        options.databasePassword = "custom-pass"
        options.dbPortNumber = 3306

        strategyDiscoveryPipeline.run(options)

        // Verify DataSourceConfig was created with custom values
        val dataSourceConfigCaptor = ArgumentCaptor.forClass(DataSourceConfig::class.java)
        verify(mockWriteFnFactory).create(dataSourceConfigCaptor.capture())

        val capturedConfig = dataSourceConfigCaptor.value
        assertThat(capturedConfig.serverName).isEqualTo("custom-host")
        assertThat(capturedConfig.databaseName).isEqualTo("custom-db")
        assertThat(capturedConfig.username).isEqualTo("custom-user")
        assertThat(capturedConfig.password).isEqualTo("custom-pass")
        assertThat(capturedConfig.portNumber).isEqualTo(3306)
        assertThat(capturedConfig.applicationName).isNull()
        assertThat(capturedConfig.connectTimeout).isNull()
        assertThat(capturedConfig.socketTimeout).isNull()
        assertThat(capturedConfig.readOnly).isNull()
    }

    @Test
    fun testFactoryInteractions() {
        strategyDiscoveryPipeline.run(options)

        // Verify that both factories are called exactly once
        verify(mockDiscoveryRequestSourceFactory, times(1)).create(options)
        verify(mockWriteFnFactory, times(1)).create(any())

        // Verify no additional interactions with mocks
        verifyNoMoreInteractions(mockDiscoveryRequestSourceFactory)
    }

    @Test
    fun testMultipleRunCallsCreateNewInstances() {
        // Run pipeline multiple times
        strategyDiscoveryPipeline.run(options)
        strategyDiscoveryPipeline.run(options)

        // Verify factories are called each time
        verify(mockDiscoveryRequestSourceFactory, times(2)).create(options)
        verify(mockWriteFnFactory, times(2)).create(any())
    }

    @Test
    fun testOptionsPassedCorrectlyToRequestSourceFactory() {
        // Create specific options to verify they're passed through correctly
        val specificOptions =
            testPipeline.options.`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
                databaseUsername = "specific_user"
                databasePassword = "specific_pass"
                dbServerName = "specific_host"
                dbDatabaseName = "specific_db"
                dbPortNumber = 1234
            }

        strategyDiscoveryPipeline.run(specificOptions)

        // Verify the exact options object was passed
        verify(mockDiscoveryRequestSourceFactory).create(specificOptions)
    }

    @Test
    fun testDependencyInjectionIntegrity() {
        // Verify all dependencies were injected correctly
        assertThat(strategyDiscoveryPipeline).isNotNull()

        // We can't directly access private fields, but we can verify behavior
        // by ensuring the pipeline can run without NullPointerExceptions
        try {
            strategyDiscoveryPipeline.run(options)
        } catch (e: NullPointerException) {
            throw AssertionError("Pipeline should not have null dependencies", e)
        }
    }

    @Test
    fun testPipelineWithDifferentOptionsCombinations() {
        // Test with minimal required options
        val minimalOptions =
            testPipeline.options.`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
                databaseUsername = "min_user"
                databasePassword = "min_pass"
                dbServerName = "localhost"
                dbDatabaseName = "test"
                dbPortNumber = 5432
            }

        strategyDiscoveryPipeline.run(minimalOptions)

        verify(mockDiscoveryRequestSourceFactory).create(minimalOptions)
        verify(mockWriteFnFactory).create(any())
    }

    @Test
    fun testErrorPropagationFromFactories() {
        // Setup factory to throw exception
        whenever(mockDiscoveryRequestSourceFactory.create(any()))
            .thenThrow(RuntimeException("Factory error"))

        // Verify exception is propagated
        try {
            strategyDiscoveryPipeline.run(options)
            fail("Should propagate factory exceptions")
        } catch (e: RuntimeException) {
            // expected
        }
    }

    @Test
    fun testErrorPropagationFromWriteFnFactory() {
        // Setup write function factory to throw exception
        whenever(mockWriteFnFactory.create(any())).thenThrow(RuntimeException("Write factory error"))

        // Verify exception is propagated
        try {
            strategyDiscoveryPipeline.run(options)
            fail("Should propagate write factory exceptions")
        } catch (e: RuntimeException) {
            // expected
        }
    }

    /** Integration test that verifies the complete flow works with real options but mocked dependencies. */
    @Test
    fun testIntegrationWithRealOptions() {
        val realOptions =
            testPipeline.options.`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
                databaseUsername = "integration_user"
                databasePassword = "integration_pass"
                dbServerName = "integration_host"
                dbDatabaseName = "integration_db"
                dbPortNumber = 5432
                kafkaBootstrapServers = "localhost:9092"
                strategyDiscoveryRequestTopic = "test-topic"
                influxDbUrl = "http://localhost:8086"
                influxDbOrg = "test-org"
                influxDbBucket = "test-bucket"
            }

        // Should complete without exceptions
        strategyDiscoveryPipeline.run(realOptions)

        // Verify all expected interactions occurred
        verify(mockDiscoveryRequestSourceFactory).create(realOptions)
        verify(mockWriteFnFactory).create(any())
    }
}

package com.verlumen.tradestream.discovery

import com.google.common.truth.Truth.assertThat
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.sql.DataSourceConfig
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.apache.beam.sdk.testing.TestPipeline
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
    @Bind
    @Mock
    lateinit var mockRunGAFn: RunGADiscoveryFn

    @Bind
    @Mock
    lateinit var mockExtractFn: ExtractDiscoveredStrategiesFn

    @Bind
    @Mock
    lateinit var mockWriteFnFactory: WriteDiscoveredStrategiesToPostgresFnFactory

    @Bind
    @Mock
    lateinit var mockDiscoveryRequestSourceFactory: DiscoveryRequestSourceFactory

    // Additional mocks for testing
    @Mock
    lateinit var mockDiscoveryRequestSource: DiscoveryRequestSource

    @Mock
    lateinit var mockWriteFn: WriteDiscoveredStrategiesToPostgresFn

    @Mock
    lateinit var mockOptions: StrategyDiscoveryPipelineOptions

    // The class under test - injected by Guice
    @Inject
    lateinit var strategyDiscoveryPipeline: StrategyDiscoveryPipeline

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Create Guice injector with BoundFieldModule to inject mocked dependencies
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)

        // Setup default mock behaviors
        setupDefaultMockBehaviors()
    }

    private fun setupDefaultMockBehaviors() {
        // Mock options with valid database configuration
        whenever(mockOptions.databaseUsername).thenReturn("test_user")
        whenever(mockOptions.databasePassword).thenReturn("test_password")
        whenever(mockOptions.dbServerName).thenReturn("localhost")
        whenever(mockOptions.dbDatabaseName).thenReturn("test_db")
        whenever(mockOptions.dbPortNumber).thenReturn(5432)

        // Mock factory returns
        whenever(mockDiscoveryRequestSourceFactory.create(any())).thenReturn(mockDiscoveryRequestSource)
        whenever(mockWriteFnFactory.create(any())).thenReturn(mockWriteFn)

        // For unit testing purposes, we're focusing on the configuration and wiring logic
    }

    @Test
    fun testPipelineInstantiation() {
        // Verify that Guice can create an instance of StrategyDiscoveryPipeline
        assertThat(strategyDiscoveryPipeline).isNotNull()
    }

    @Test
    fun testValidOptionsProcessing() {
        // Test that valid options are processed correctly
        strategyDiscoveryPipeline.run(mockOptions)

        // Verify that factories were called with correct parameters
        verify(mockDiscoveryRequestSourceFactory).create(mockOptions)

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
        whenever(mockOptions.databaseUsername).thenReturn(null)

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(mockOptions)
            fail("Should throw exception when database username is null")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testNullDatabasePasswordThrowsException() {
        // Setup options with null password
        whenever(mockOptions.databasePassword).thenReturn(null)

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(mockOptions)
            fail("Should throw exception when database password is null")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testEmptyDatabaseUsernameThrowsException() {
        // Setup options with empty username
        whenever(mockOptions.databaseUsername).thenReturn("")

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(mockOptions)
            fail("Should throw exception when database username is empty")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testEmptyDatabasePasswordThrowsException() {
        // Setup options with empty password
        whenever(mockOptions.databasePassword).thenReturn("")

        // Verify that pipeline throws IllegalArgumentException
        try {
            strategyDiscoveryPipeline.run(mockOptions)
            fail("Should throw exception when database password is empty")
        } catch (e: IllegalArgumentException) {
            // expected
        }
    }

    @Test
    fun testDataSourceConfigurationCreation() {
        // Setup options with all configuration values
        whenever(mockOptions.dbServerName).thenReturn("custom-host")
        whenever(mockOptions.dbDatabaseName).thenReturn("custom-db")
        whenever(mockOptions.databaseUsername).thenReturn("custom-user")
        whenever(mockOptions.databasePassword).thenReturn("custom-pass")
        whenever(mockOptions.dbPortNumber).thenReturn(3306)

        strategyDiscoveryPipeline.run(mockOptions)

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
        strategyDiscoveryPipeline.run(mockOptions)

        // Verify that both factories are called exactly once
        verify(mockDiscoveryRequestSourceFactory, times(1)).create(mockOptions)
        verify(mockWriteFnFactory, times(1)).create(any())

        // Verify no additional interactions with mocks
        verifyNoMoreInteractions(mockDiscoveryRequestSourceFactory)
    }

    @Test
    fun testMultipleRunCallsCreateNewInstances() {
        // Run pipeline multiple times
        strategyDiscoveryPipeline.run(mockOptions)
        strategyDiscoveryPipeline.run(mockOptions)

        // Verify factories are called each time
        verify(mockDiscoveryRequestSourceFactory, times(2)).create(mockOptions)
        verify(mockWriteFnFactory, times(2)).create(any())
    }

    @Test
    fun testOptionsPassedCorrectlyToRequestSourceFactory() {
        // Create specific options to verify they're passed through correctly
        val specificOptions =
            PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
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
            strategyDiscoveryPipeline.run(mockOptions)
        } catch (e: NullPointerException) {
            throw AssertionError("Pipeline should not have null dependencies", e)
        }
    }

    @Test
    fun testPipelineWithDifferentOptionsCombinations() {
        // Test with minimal required options
        val minimalOptions =
            PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
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
            strategyDiscoveryPipeline.run(mockOptions)
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
            strategyDiscoveryPipeline.run(mockOptions)
            fail("Should propagate write factory exceptions")
        } catch (e: RuntimeException) {
            // expected
        }
    }

    /** Integration test that verifies the complete flow works with real options but mocked dependencies. */
    @Test
    fun testIntegrationWithRealOptions() {
        val realOptions =
            PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
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

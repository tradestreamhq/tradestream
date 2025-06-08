package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever

/**
 * Unit tests for the main StrategyDiscoveryPipeline wiring.
 *
 * These tests focus on pipeline construction and Guice integration
 * rather than end-to-end execution.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineTest {
    @Mock
    lateinit var mockOptions: StrategyDiscoveryPipelineOptions

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Configure mock options with required values
        whenever(mockOptions.kafkaBootstrapServers).thenReturn("localhost:9092")
        whenever(mockOptions.strategyDiscoveryRequestTopic).thenReturn("test-topic")
        whenever(mockOptions.dbServerName).thenReturn("localhost")
        whenever(mockOptions.dbDatabaseName).thenReturn("test-db")
        whenever(mockOptions.dbPortNumber).thenReturn(5432)
        whenever(mockOptions.databaseUsername).thenReturn("user")
        whenever(mockOptions.databasePassword).thenReturn("pass")
    }

    @Test
    fun testCreateInjectorWithParameterlessModule() {
        // Injector should build with the default module
        val injector = Guice.createInjector(DiscoveryModule())
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory != null) { "Factory should be instantiable" }
    }

    @Test
    fun testFactoryCreatesValidPipeline() {
        val injector = Guice.createInjector(DiscoveryModule())
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)

        val pipeline = factory.create(mockOptions)
        assert(pipeline != null) { "Pipeline should be created successfully" }
    }

    @Test
    fun testTransformInstantiation() {
        val injector = Guice.createInjector(DiscoveryModule())
        assert(injector.getInstance(DeserializeStrategyDiscoveryRequestFn::class.java) != null)
        assert(injector.getInstance(ExtractDiscoveredStrategiesFn::class.java) != null)
        assert(injector.getInstance(WriteDiscoveredStrategiesToPostgresFnFactory::class.java) != null)
    }

    @Test
    fun testFactoryWithRealOptions() {
        val realOptions =
            PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java).apply {
                kafkaBootstrapServers = "localhost:9092"
                strategyDiscoveryRequestTopic = "test-topic"
                databaseUsername = "user"
                databasePassword = "password"
            }

        val injector = Guice.createInjector(DiscoveryModule())
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory.create(realOptions) != null)
    }
}

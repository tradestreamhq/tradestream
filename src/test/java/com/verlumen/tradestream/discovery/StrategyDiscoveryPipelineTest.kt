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
 * Unit tests for the main StrategyDiscoveryPipeline.
 *
 * These tests focus on the pipeline construction and Guice integration
 * rather than end-to-end pipeline execution.
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
    }

    @Test
    fun testCreateInjectorWithParameterlessModule() {
        // Test that the injector can be created with parameterless DiscoveryModule
        val injector = Guice.createInjector(DiscoveryModule())

        // Verify that the factory can be instantiated
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory != null) { "Factory should be instantiable" }
    }

    @Test
    fun testFactoryCreatesValidPipeline() {
        val injector = Guice.createInjector(DiscoveryModule())
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)

        // Test that the factory can create a pipeline with valid options
        val pipeline = factory.create(mockOptions)
        assert(pipeline != null) { "Pipeline should be created successfully" }
    }

    @Test
    fun testTransformInstantiation() {
        val injector = Guice.createInjector(DiscoveryModule())

        // Test that all transform classes can be instantiated
        val deserializeFn = injector.getInstance(DeserializeStrategyDiscoveryRequestFn::class.java)
        assert(deserializeFn != null) { "DeserializeStrategyDiscoveryRequestFn should be instantiable" }

        val extractFn = injector.getInstance(ExtractDiscoveredStrategiesFn::class.java)
        assert(extractFn != null) { "ExtractDiscoveredStrategiesFn should be instantiable" }

        val postgresFn = injector.getInstance(WriteDiscoveredStrategiesToPostgresFn::class.java)
        assert(postgresFn != null) { "WriteDiscoveredStrategiesToPostgresFn should be instantiable" }
    }

    @Test
    fun testFactoryWithRealOptions() {
        // Test with real options instead of mocks
        val realOptions = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java)
        realOptions.kafkaBootstrapServers = "localhost:9092"
        realOptions.strategyDiscoveryRequestTopic = "test-topic"

        val injector = Guice.createInjector(DiscoveryModule())
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)

        val pipeline = factory.create(realOptions)
        assert(pipeline != null) { "Pipeline should be created with real options" }
    }

    @Test
    fun testMainMethodExists() {
        // Verify that the main method exists and can be called reflectively
        val mainMethod = StrategyDiscoveryPipeline::class.java.getMethod("main", Array<String>::class.java)
        assert(mainMethod != null) { "Main method should exist" }
        assert(
            java.lang.reflect.Modifier
                .isStatic(mainMethod.modifiers),
        ) { "Main method should be static" }
    }
}

package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations

/**
 * Unit tests for the main StrategyDiscoveryPipeline.
 * 
 * These tests focus on the pipeline construction and Guice integration
 * rather than end-to-end pipeline execution.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineTest {

    @Bind @Mock
    lateinit var mockOptions: StrategyDiscoveryPipelineOptions

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        
        // Configure mock options with required values
        org.mockito.kotlin.whenever(mockOptions.databaseJdbcUrl).thenReturn("jdbc:postgresql://test:5432/test")
        org.mockito.kotlin.whenever(mockOptions.databaseUsername).thenReturn("test")
        org.mockito.kotlin.whenever(mockOptions.databasePassword).thenReturn("test")
        org.mockito.kotlin.whenever(mockOptions.influxDbUrl).thenReturn("http://test:8086")
        org.mockito.kotlin.whenever(mockOptions.influxDbToken).thenReturn("test-token")
        org.mockito.kotlin.whenever(mockOptions.influxDbOrg).thenReturn("test-org")
        org.mockito.kotlin.whenever(mockOptions.influxDbBucket).thenReturn("test-bucket")
        org.mockito.kotlin.whenever(mockOptions.kafkaBootstrapServers).thenReturn("localhost:9092")
        org.mockito.kotlin.whenever(mockOptions.strategyDiscoveryRequestTopic).thenReturn("test-topic")
    }

    @Test
    fun testCreateInjectorWithValidOptions() {
        // Test that the injector can be created with valid options
        val injector = Guice.createInjector(StrategyDiscoveryModule(mockOptions))
        
        // Verify that basic bindings work
        val options = injector.getInstance(StrategyDiscoveryPipelineOptions::class.java)
        assert(options === mockOptions) { "Should bind the provided options instance" }
        
        // Verify that data source can be created
        val dataSource = injector.getInstance(javax.sql.DataSource::class.java)
        assert(dataSource != null) { "DataSource should be injectable" }
        
        // Verify that InfluxDB fetcher can be created  
        val candleFetcher = injector.getInstance(com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher::class.java)
        assert(candleFetcher != null) { "InfluxDbCandleFetcher should be injectable" }
    }

    @Test
    fun testTransformInstantiation() {
        val injector = Guice.createInjector(StrategyDiscoveryModule(mockOptions))
        
        // Test that all transform classes can be instantiated
        val deserializeFn = injector.getInstance(DeserializeStrategyDiscoveryRequestFn::class.java)
        assert(deserializeFn != null) { "DeserializeStrategyDiscoveryRequestFn should be instantiable" }

        val extractFn = injector.getInstance(ExtractDiscoveredStrategiesFn::class.java)
        assert(extractFn != null) { "ExtractDiscoveredStrategiesFn should be instantiable" }

        val postgresFn = injector.getInstance(WriteDiscoveredStrategiesToPostgresFn::class.java)
        assert(postgresFn != null) { "WriteDiscoveredStrategiesToPostgresFn should be instantiable" }
    }

    @Test
    fun testPipelineOptionsValidation() {
        // Test with invalid options
        val invalidOptions = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java)
        // Don't set required fields
        
        val injector = Guice.createInjector(StrategyDiscoveryModule(invalidOptions))
        
        // Should fail when trying to create DataSource without required config
        try {
            injector.getInstance(javax.sql.DataSource::class.java)
            assert(false) { "Should fail with missing database configuration" }
        } catch (e: Exception) {
            // Expected - missing configuration should cause failure
            assert(e.message?.contains("required") == true || 
                   e.cause?.message?.contains("required") == true) {
                "Error should mention missing required configuration"
            }
        }
    }

    @Test 
    fun testMainMethodExists() {
        // Verify that the main method exists and can be called reflectively
        val mainMethod = StrategyDiscoveryPipeline::class.java.getMethod("main", Array<String>::class.java)
        assert(mainMethod != null) { "Main method should exist" }
        assert(java.lang.reflect.Modifier.isStatic(mainMethod.modifiers)) { "Main method should be static" }
    }
}

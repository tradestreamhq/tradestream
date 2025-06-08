package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.backtesting.BacktestRequestFactory
import com.verlumen.tradestream.backtesting.BacktestRunner
import org.apache.beam.sdk.options.PipelineOptionsFactory
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.whenever

/**
 * Unit tests for StrategyDiscoveryPipeline wiring.
 *
 * `BoundFieldModule` automatically binds all @Mock fields into the Guice injector,
 * satisfying the dependencies that DiscoveryModule expects.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineTest {

    // ----- Beam pipeline options ---------------------------------------------------------------
    @Mock lateinit var mockOptions: StrategyDiscoveryPipelineOptions

    // ----- Back-testing dependencies required by FitnessFunctionFactoryImpl ---------------------
    @Mock lateinit var backtestRequestFactory: BacktestRequestFactory
    @Mock lateinit var backtestRunner: BacktestRunner

    // Injector that includes the mocks and production bindings.
    private val injector by lazy {
        Guice.createInjector(
            BoundFieldModule.of(this), // binds @Mock fields
            DiscoveryModule(),
        )
    }

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)

        // Minimal configuration for the mocked pipeline options
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
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory != null) { "Factory should be instantiable" }
    }

    @Test
    fun testFactoryCreatesValidPipeline() {
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        val pipeline = factory.create(mockOptions)
        assert(pipeline != null) { "Pipeline should be created successfully" }
    }

    @Test
    fun testTransformInstantiation() {
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
                dbServerName = "localhost"
                dbDatabaseName = "test-db"
                dbPortNumber = 5432
                databaseUsername = "user"
                databasePassword = "password"
            }

        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory.create(realOptions) != null)
    }
}

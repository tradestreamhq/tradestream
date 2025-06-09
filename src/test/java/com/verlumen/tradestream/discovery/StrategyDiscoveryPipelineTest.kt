package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
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
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever

/**
 * Unit tests for StrategyDiscoveryPipeline wiring.
 *
 * `BoundFieldModule` automatically binds all @Mock fields into the Guice injector,
 * satisfying the dependencies without using production modules.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineTest {
    // ----- Beam pipeline options ---------------------------------------------------------------
    @Mock lateinit var mockOptions: StrategyDiscoveryPipelineOptions

    // ----- Back-testing dependencies required by FitnessFunctionFactoryImpl ---------------------
    @Bind @Mock
    lateinit var backtestRequestFactory: BacktestRequestFactory

    @Bind @Mock
    lateinit var backtestRunner: BacktestRunner

    // ----- Mock the pipeline components directly -----------------------------------------------
    @Bind @Mock
    lateinit var deserializeStrategyDiscoveryRequestFn: DeserializeStrategyDiscoveryRequestFn

    @Bind @Mock
    lateinit var runGADiscoveryFn: RunGADiscoveryFn

    @Bind @Mock
    lateinit var extractDiscoveredStrategiesFn: ExtractDiscoveredStrategiesFn

    @Bind @Mock
    lateinit var discoveredStrategySink: DiscoveredStrategySink

    @Bind @Mock
    lateinit var strategyDiscoveryPipelineFactory: StrategyDiscoveryPipelineFactory

    // Mock pipeline instance
    @Mock lateinit var mockPipeline: StrategyDiscoveryPipeline

    // Injector that includes only the mocks
    private val injector by lazy {
        Guice.createInjector(
            BoundFieldModule.of(this),
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

        // Configure the factory mock to return our mock pipeline
        whenever(strategyDiscoveryPipelineFactory.create(any())).thenReturn(mockPipeline)
    }

    @Test
    fun testCreateInjectorWithMockedDependencies() {
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory != null) { "Factory should be instantiable" }
    }

    @Test
    fun testFactoryCreatesValidPipeline() {
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        val pipeline = factory.create(mockOptions)
        assert(pipeline != null) { "Pipeline should be created successfully" }
        assert(pipeline == mockPipeline) { "Should return the mocked pipeline instance" }
    }

    @Test
    fun testTransformInstantiation() {
        assert(injector.getInstance(DeserializeStrategyDiscoveryRequestFn::class.java) != null)
        assert(injector.getInstance(ExtractDiscoveredStrategiesFn::class.java) != null)
        assert(injector.getInstance(DiscoveredStrategySink::class.java) != null)
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
        val pipeline = factory.create(realOptions)
        assert(pipeline != null) { "Pipeline should be created successfully" }
        assert(pipeline == mockPipeline) { "Should return the mocked pipeline instance" }
    }
}

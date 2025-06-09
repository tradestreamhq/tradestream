package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.backtesting.BacktestRequestFactory
import com.verlumen.tradestream.backtesting.BacktestRunner
import com.verlumen.tradestream.execution.RunMode
import org.apache.beam.sdk.testing.TestPipeline
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.verify
import org.mockito.kotlin.whenever

/**
 * Unit tests for StrategyDiscoveryPipeline wiring.
 *
 * `BoundFieldModule` automatically binds all @Mock fields into the Guice injector,
 * satisfying the dependencies without using production modules.
 */
@RunWith(JUnit4::class)
class StrategyDiscoveryPipelineTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    // ----- Back-testing dependencies required by FitnessFunctionFactoryImpl ---------------------
    @Bind @Mock
    lateinit var backtestRequestFactory: BacktestRequestFactory

    @Bind @Mock
    lateinit var backtestRunner: BacktestRunner

    // ----- Mock the pipeline components directly -----------------------------------------------
    @Bind @Mock
    lateinit var discoveryRequestSource: DiscoveryRequestSource

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
        whenever(strategyDiscoveryPipelineFactory.create()).thenReturn(mockPipeline)
    }

    @Test
    fun testCreateInjectorWithMockedDependencies() {
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        assert(factory != null) { "Factory should be instantiable" }
    }

    @Test
    fun testFactoryCreatesValidPipeline() {
        val factory = injector.getInstance(StrategyDiscoveryPipelineFactory::class.java)
        val pipeline = factory.create()
        assert(pipeline != null) { "Pipeline should be created successfully" }
        assert(pipeline == mockPipeline) { "Should return the mocked pipeline instance" }
    }

    @Test
    fun testTransformInstantiation() {
        assert(injector.getInstance(DiscoveryRequestSource::class.java) != null)
        assert(injector.getInstance(RunGADiscoveryFn::class.java) != null)
        assert(injector.getInstance(ExtractDiscoveredStrategiesFn::class.java) != null)
        assert(injector.getInstance(DiscoveredStrategySink::class.java) != null)
    }

    @Test
    fun testPipelineRunsInDryMode() {
        val pipeline =
            StrategyDiscoveryPipeline(
                pipeline = this.pipeline,
                runMode = RunMode.DRY,
                discoveryRequestSource = discoveryRequestSource,
                runGAFn = runGADiscoveryFn,
                extractFn = extractDiscoveredStrategiesFn,
                discoveredStrategySink = discoveredStrategySink,
            )

        pipeline.run()

        verify(discoveryRequestSource).expand(any())
        verify(runGADiscoveryFn).expand(any())
        verify(extractDiscoveredStrategiesFn).expand(any())
        verify(discoveredStrategySink).expand(any())
    }
}

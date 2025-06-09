package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.MockitoAnnotations

@RunWith(JUnit4::class)
class DryRunDiscoveryRequestSourceTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Inject
    lateinit var dryRunSource: DryRunDiscoveryRequestSource

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)
    }

    @Test
    fun testDryRunSourceGeneratesRequests() {
        val input = pipeline.apply(Create.of(Unit))
        val output: PCollection<StrategyDiscoveryRequest> = input.apply(dryRunSource)

        PAssert.that(output).satisfies { requests ->
            val requestList = requests.toList()
            assert(requestList.isNotEmpty()) { "Should generate at least one request" }

            // Verify request structure
            requestList.forEach { request ->
                assert(request.symbol.isNotEmpty()) { "Request should have a symbol" }
                assert(request.hasStartTime()) { "Request should have a start time" }
                assert(request.hasEndTime()) { "Request should have an end time" }
                assert(request.hasStrategyType()) { "Request should have a strategy type" }
                assert(request.hasTopN()) { "Request should have topN" }
                assert(request.hasGaConfig()) { "Request should have GA config" }
            }

            // Verify we have requests for different strategy types
            val strategyTypes = requestList.map { it.strategyType }.toSet()
            assert(strategyTypes.contains(StrategyType.SMA_RSI)) { "Should include SMA_RSI strategy" }
            assert(strategyTypes.contains(StrategyType.EMA_MACD)) { "Should include EMA_MACD strategy" }

            null
        }

        pipeline.run().waitUntilFinish()
    }
} 

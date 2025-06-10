package com.verlumen.tradestream.discovery

import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.util.JsonFormat
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.strategies.StrategyType
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import org.mockito.MockitoAnnotations

@RunWith(JUnit4::class)
class ParseDiscoveryRequestsTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Inject
    lateinit var parseFn: ParseDiscoveryRequests

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)
    }

    @Test
    fun testParseValidRequest() {
        val request =
            StrategyDiscoveryRequest
                .newBuilder()
                .setSymbol("BTC/USD")
                .setStartTime(Timestamps.fromMillis(System.currentTimeMillis() - 100000))
                .setEndTime(Timestamps.fromMillis(System.currentTimeMillis()))
                .setStrategyType(StrategyType.SMA_RSI)
                .setTopN(10)
                .setGaConfig(
                    GAConfig
                        .newBuilder()
                        .setMaxGenerations(50)
                        .setPopulationSize(100)
                        .build(),
                ).build()

        val jsonRequest = JsonFormat.printer().print(request)
        val input: PCollection<String> = pipeline.apply(Create.of(listOf(jsonRequest)))
        val output: PCollection<StrategyDiscoveryRequest> = input.apply(parseFn)

        PAssert.that(output).satisfies { requests ->
            val requestList = requests.toList()
            assert(requestList.size == 1) { "Should parse exactly one request" }

            val parsedRequest = requestList[0]
            assert(parsedRequest.symbol == "BTC/USD") { "Should parse symbol correctly" }
            assert(parsedRequest.strategyType == StrategyType.SMA_RSI) { "Should parse strategy type correctly" }
            assert(parsedRequest.topN == 10) { "Should parse topN correctly" }
            assert(parsedRequest.gaConfig.maxGenerations == 50) { "Should parse GA config correctly" }
            assert(parsedRequest.gaConfig.populationSize == 100) { "Should parse GA config correctly" }

            null
        }

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testParseInvalidRequest() {
        val input: PCollection<String> = pipeline.apply(Create.of(listOf("not-a-json")))
        val output: PCollection<StrategyDiscoveryRequest> = input.apply(parseFn)

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testParseEmptyRequest() {
        val input: PCollection<String> = pipeline.apply(Create.of(listOf("")))
        val output: PCollection<StrategyDiscoveryRequest> = input.apply(parseFn)

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
} 

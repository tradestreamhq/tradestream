package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.inject.Guice
import com.google.inject.Inject
import com.google.inject.testing.fieldbinder.Bind
import com.google.inject.testing.fieldbinder.BoundFieldModule
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import io.jenetics.DoubleChromosome
import io.jenetics.DoubleGene
import io.jenetics.Genotype
import io.jenetics.Phenotype
import io.jenetics.engine.Engine
import io.jenetics.engine.EvolutionResult
import io.jenetics.engine.EvolutionStream
import io.jenetics.util.ISeq
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
import org.mockito.Mock
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.anyLong
import org.mockito.kotlin.eq
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import java.util.stream.Collector

@RunWith(JUnit4::class)
class RunGADiscoveryFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Bind @Mock
    lateinit var mockCandleFetcher: InfluxDbCandleFetcher

    @Bind @Mock
    lateinit var mockGaEngineFactory: GAEngineFactory

    @Bind @Mock
    lateinit var mockGenotypeConverter: GenotypeConverter

    @Mock
    lateinit var mockEngine: Engine<DoubleGene, Double>

    @Inject
    lateinit var runGADiscoveryFn: RunGADiscoveryFn

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        val injector = Guice.createInjector(BoundFieldModule.of(this))
        injector.injectMembers(this)
    }

    private fun createTestRequest(): StrategyDiscoveryRequest {
        val now = System.currentTimeMillis()
        return StrategyDiscoveryRequest.newBuilder()
            .setSymbol("BTC/USD")
            .setStartTime(Timestamps.fromMillis(now - 200000))
            .setEndTime(Timestamps.fromMillis(now - 100000))
            .setStrategyType(StrategyType.SMA_RSI)
            .setTopN(1)
            .setGaConfig(
                GAConfig.newBuilder()
                    .setMaxGenerations(10)
                    .setPopulationSize(20)
                    .build()
            ).build()
    }

    private fun createDummyCandle(timestamp: Timestamp): Candle =
        Candle.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair("BTC/USD")
            .setOpen(100.0)
            .setHigh(110.0)
            .setLow(90.0)
            .setClose(105.0)
            .setVolume(1000.0)
            .build()

    @Test
    fun testRunGADiscoveryFn_success() {
        val request = createTestRequest()
        val dummyCandle = createDummyCandle(request.startTime)
        val candles = ImmutableList.of(dummyCandle)

        val smaRsiParams = SmaRsiParameters.newBuilder()
            .setMovingAveragePeriod(10)
            .setRsiPeriod(14)
            .setOverboughtThreshold(70.0)
            .setOversoldThreshold(30.0)
            .build()
        val paramsAny = Any.pack(smaRsiParams)

        val genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0))
        val phenotype = Phenotype.of(genotype, 1, 10.5)

        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(candles)
        whenever(mockGaEngineFactory.createEngine(any<GAEngineParams>())).thenReturn(mockEngine)

        val mockEvolutionResult: EvolutionResult<DoubleGene, Double> = mock()
        val mockEvolutionStream: EvolutionStream<DoubleGene, Double> = mock()

        whenever(mockEngine.stream()).thenReturn(mockEvolutionStream)
        whenever(mockEvolutionStream.limit(anyLong())).thenReturn(mockEvolutionStream)
        whenever(mockEvolutionStream.collect(any())).thenReturn(mockEvolutionResult)
        whenever(mockEvolutionResult.population()).thenReturn(ISeq.of(phenotype))

        whenever(mockGenotypeConverter.convertToParameters(any(), eq(StrategyType.SMA_RSI)))
            .thenReturn(paramsAny)

        val input: PCollection<StrategyDiscoveryRequest> = pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        val expectedStrategy = DiscoveredStrategy.newBuilder()
            .setStrategy(Strategy.newBuilder().setType(StrategyType.SMA_RSI).setParameters(paramsAny))
            .setScore(10.5)
            .setSymbol("BTC/USD")
            .setStartTime(request.startTime)
            .setEndTime(request.endTime)
            .build()
        val expectedResult = StrategyDiscoveryResult.newBuilder().addTopStrategies(expectedStrategy).build()

        PAssert.that(output).containsInAnyOrder(expectedResult)
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testRunGADiscoveryFn_noCandles() {
        val request = createTestRequest()
        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(ImmutableList.of())

        val input: PCollection<StrategyDiscoveryRequest> = pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testRunGADiscoveryFn_gaYieldsNoResults() {
        val request = createTestRequest()
        val dummyCandle = createDummyCandle(request.startTime)
        val candles = ImmutableList.of(dummyCandle)

        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(candles)
        whenever(mockGaEngineFactory.createEngine(any<GAEngineParams>())).thenReturn(mockEngine)

        val mockEvolutionResultEmpty: EvolutionResult<DoubleGene, Double> = mock()
        val mockEvolutionStreamEmpty: EvolutionStream<DoubleGene, Double> = mock()

        whenever(mockEngine.stream()).thenReturn(mockEvolutionStreamEmpty)
        whenever(mockEvolutionStreamEmpty.limit(anyLong())).thenReturn(mockEvolutionStreamEmpty)
        whenever(mockEvolutionStreamEmpty.collect(any())).thenReturn(mockEvolutionResultEmpty)
        whenever(mockEvolutionResultEmpty.population()).thenReturn(ISeq.empty())

        val input: PCollection<StrategyDiscoveryRequest> = pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}

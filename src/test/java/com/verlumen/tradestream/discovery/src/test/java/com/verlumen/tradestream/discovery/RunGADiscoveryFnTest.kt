package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.backtesting.GAEngineFactory
import com.verlumen.tradestream.backtesting.GAOptimizationRequest
import com.verlumen.tradestream.backtesting.GenotypeConverter
import com.verlumen.tradestream.discovery.proto.Discovery.GAConfig
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryRequest
import com.verlumen.tradestream.discovery.proto.Discovery.StrategyDiscoveryResult
import com.verlumen.tradestream.discovery.proto.Discovery.DiscoveredStrategy
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.marketdata.InfluxDbCandleFetcher
import com.verlumen.tradestream.strategies.SmaRsiParameters
import com.verlumen.tradestream.strategies.Strategy
import com.verlumen.tradestream.strategies.StrategyType
import io.jenetics.*
import io.jenetics.engine.Engine
import io.jenetics.engine.EvolutionResult
import org.apache.beam.sdk.options.PipelineOptionsFactory
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
import org.mockito.Mockito.*
import org.mockito.MockitoAnnotations
import org.mockito.kotlin.any
import org.mockito.kotlin.whenever
import java.time.Instant

@RunWith(JUnit4::class)
class RunGADiscoveryFnTest {

    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create()

    @Mock private lateinit var mockCandleFetcher: InfluxDbCandleFetcher
    @Mock private lateinit var mockGaEngineFactory: GAEngineFactory
    @Mock private lateinit var mockGenotypeConverter: GenotypeConverter
    @Mock private lateinit var mockEngine: Engine<DoubleGene, Double> // Adjust Gene type if necessary

    private lateinit var options: StrategyDiscoveryPipelineOptions

    @Before
    fun setUp() {
        MockitoAnnotations.openMocks(this)
        options = PipelineOptionsFactory.create().`as`(StrategyDiscoveryPipelineOptions::class.java)
        options.influxDbUrl = "http://fake-influxdb:8086"
        options.influxDbToken = "fake-token"
        options.influxDbOrg = "fake-org"
        options.influxDbBucket = "fake-bucket"
    }

    private fun createTestRequest(): StrategyDiscoveryRequest {
        val now = System.currentTimeMillis()
        return StrategyDiscoveryRequest.newBuilder()
            .setSymbol("BTC/USD")
            .setStartTime(Timestamps.fromMillis(now - 200000))
            .setEndTime(Timestamps.fromMillis(now - 100000))
            .setStrategyType(StrategyType.SMA_RSI)
            .setTopN(1)
            .setGaConfig(GAConfig.newBuilder().setMaxGenerations(10).setPopulationSize(20).build())
            .build()
    }

    private fun createDummyCandle(timestamp: Timestamp): Candle {
        return Candle.newBuilder()
            .setTimestamp(timestamp)
            .setCurrencyPair("BTC/USD")
            .setOpen(100.0)
            .setHigh(110.0)
            .setLow(90.0)
            .setClose(105.0)
            .setVolume(1000.0)
            .build()
    }

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

        val genotype = Genotype.of(DoubleChromosome.of(0.0, 1.0)) // Example genotype
        val phenotype = Phenotype.of(genotype, 1, 10.5) // fitness 10.5

        whenever(mockCandleFetcher.fetchCandles(any(), any(), any())).thenReturn(candles)
        whenever(mockGaEngineFactory.createEngine(any<GAOptimizationRequest>())).thenReturn(mockEngine as Engine<*, Double>?)

        // Mock the stream().limit().collect() chain
        val evolutionResultStream = mock(java.util.stream.Stream::class.java) as java.util.stream.Stream<EvolutionResult<DoubleGene, Double>>
        val limitedStream = mock(java.util.stream.Stream::class.java) as java.util.stream.Stream<EvolutionResult<DoubleGene, Double>>

        whenever(mockEngine.stream()).thenReturn(evolutionResultStream)
        whenever(evolutionResultStream.limit(anyLong())).thenReturn(limitedStream)
        whenever(limitedStream.collect(EvolutionResult.toBestPhenotypes<DoubleGene, Double>())).thenReturn(listOf(phenotype as Phenotype<*, Double>))


        whenever(mockGenotypeConverter.convertToParameters(any<Genotype<*>>(), eq(StrategyType.SMA_RSI)))
            .thenReturn(paramsAny)

        val runGADiscoveryFn = RunGADiscoveryFn(options)
        // Manually inject mocks for testing as @Setup DI is complex for DoFn unit tests without a test harness
        val candleFetcherField = RunGADiscoveryFn::class.java.getDeclaredField("candleFetcher")
        candleFetcherField.isAccessible = true
        candleFetcherField.set(runGADiscoveryFn, mockCandleFetcher)

        val gaEngineFactoryField = RunGADiscoveryFn::class.java.getDeclaredField("gaEngineFactory")
        gaEngineFactoryField.isAccessible = true
        gaEngineFactoryField.set(runGADiscoveryFn, mockGaEngineFactory)

        val genotypeConverterField = RunGADiscoveryFn::class.java.getDeclaredField("genotypeConverter")
        genotypeConverterField.isAccessible = true
        genotypeConverterField.set(runGADiscoveryFn, mockGenotypeConverter)


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

        val runGADiscoveryFn = RunGADiscoveryFn(options)
        val candleFetcherField = RunGADiscoveryFn::class.java.getDeclaredField("candleFetcher")
        candleFetcherField.isAccessible = true
        candleFetcherField.set(runGADiscoveryFn, mockCandleFetcher)
        // GA components won't be called if no candles
        val gaEngineFactoryField = RunGADiscoveryFn::class.java.getDeclaredField("gaEngineFactory")
        gaEngineFactoryField.isAccessible = true
        gaEngineFactoryField.set(runGADiscoveryFn, mockGaEngineFactory)

        val genotypeConverterField = RunGADiscoveryFn::class.java.getDeclaredField("genotypeConverter")
        genotypeConverterField.isAccessible = true
        genotypeConverterField.set(runGADiscoveryFn, mockGenotypeConverter)

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
        whenever(mockGaEngineFactory.createEngine(any<GAOptimizationRequest>())).thenReturn(mockEngine as Engine<*, Double>?)

        // Mock the stream().limit().collect() chain to return empty list
        val evolutionResultStream = mock(java.util.stream.Stream::class.java) as java.util.stream.Stream<EvolutionResult<DoubleGene, Double>>
        val limitedStream = mock(java.util.stream.Stream::class.java) as java.util.stream.Stream<EvolutionResult<DoubleGene, Double>>
        whenever(mockEngine.stream()).thenReturn(evolutionResultStream)
        whenever(evolutionResultStream.limit(anyLong())).thenReturn(limitedStream)
        whenever(limitedStream.collect(EvolutionResult.toBestPhenotypes<DoubleGene, Double>())).thenReturn(emptyList()) // No phenotypes

        val runGADiscoveryFn = RunGADiscoveryFn(options)
        val candleFetcherField = RunGADiscoveryFn::class.java.getDeclaredField("candleFetcher")
        candleFetcherField.isAccessible = true
        candleFetcherField.set(runGADiscoveryFn, mockCandleFetcher)

        val gaEngineFactoryField = RunGADiscoveryFn::class.java.getDeclaredField("gaEngineFactory")
        gaEngineFactoryField.isAccessible = true
        gaEngineFactoryField.set(runGADiscoveryFn, mockGaEngineFactory)
         val genotypeConverterField = RunGADiscoveryFn::class.java.getDeclaredField("genotypeConverter")
         genotypeConverterField.isAccessible = true
         genotypeConverterField.set(runGADiscoveryFn, mockGenotypeConverter)


        val input: PCollection<StrategyDiscoveryRequest> = pipeline.apply(Create.of(request))
        val output: PCollection<StrategyDiscoveryResult> = input.apply(ParDo.of(runGADiscoveryFn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}

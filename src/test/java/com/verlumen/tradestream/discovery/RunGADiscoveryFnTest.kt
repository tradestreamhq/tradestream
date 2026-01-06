package com.verlumen.tradestream.discovery

import com.google.common.collect.ImmutableList
import com.google.protobuf.Any
import com.google.protobuf.Timestamp
import com.google.protobuf.util.Timestamps
import com.verlumen.tradestream.marketdata.Candle
import com.verlumen.tradestream.marketdata.CandleFetcher
import com.verlumen.tradestream.strategies.SmaRsiParameters
import io.jenetics.DoubleChromosome
import io.jenetics.DoubleGene
import io.jenetics.Genotype
import io.jenetics.engine.Engine
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.transforms.Create
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.PCollection
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4
import java.io.Serializable

/**
 * Lightweight, fully‑serializable stub for [GAEngineFactory].
 * It builds a fresh Jenetics [Engine] on every invocation to avoid holding
 * non‑serialisable state inside the DoFn payload.
 */
private class StubGAEngineFactory(
    private val empty: Boolean = false,
) : GAEngineFactory,
    Serializable {
    companion object {
        private const val serialVersionUID: Long = 1L
    }

    override fun createEngine(params: GAEngineParams): Engine<*, Double> =
        if (empty) {
            Engine
                .builder<DoubleGene, Double>({ 0.0 }, Genotype.of(DoubleChromosome.of(0.0, 1.0, 1)))
                .populationSize(1)
                .build()
        } else {
            Engine
                .builder<DoubleGene, Double>({ gt -> gt.chromosome()[0].allele() }, Genotype.of(DoubleChromosome.of(0.0, 1.0, 1)))
                .populationSize(5)
                .build()
        }
}

/** Simple serialisable [CandleFetcher] whose behaviour is configurable. */
private class StubCandleFetcher(
    private val empty: Boolean = false,
) : CandleFetcher,
    Serializable {
    companion object {
        private const val serialVersionUID: Long = 1L
    }

    override fun fetchCandles(
        symbol: String,
        startTime: Timestamp,
        endTime: Timestamp,
    ): ImmutableList<Candle> = if (empty) ImmutableList.of() else ImmutableList.of(createDummyCandle(symbol, startTime))

    private fun createDummyCandle(
        symbol: String,
        ts: Timestamp,
    ): Candle =
        Candle
            .newBuilder()
            .setTimestamp(ts)
            .setCurrencyPair(symbol)
            .setOpen(100.0)
            .setHigh(110.0)
            .setLow(90.0)
            .setClose(105.0)
            .setVolume(1_000.0)
            .build()
}

/** Trivial serialisable [GenotypeConverter] returning fixed SMA‑RSI params. */
private class StubGenotypeConverter :
    GenotypeConverter,
    Serializable {
    companion object {
        private const val serialVersionUID: Long = 1L
    }

    override fun convertToParameters(
        genotype: Genotype<*>,
        strategyName: String,
    ): Any =
        Any.pack(
            SmaRsiParameters
                .newBuilder()
                .setMovingAveragePeriod(10)
                .setRsiPeriod(14)
                .setOverboughtThreshold(70.0)
                .setOversoldThreshold(30.0)
                .build(),
        )
}

@RunWith(JUnit4::class)
class RunGADiscoveryFnTest {
    @get:Rule
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    // ----------------------------------------------------------------------
    // Helper builders
    // ----------------------------------------------------------------------

    private fun newRequest(topN: Int = 1): StrategyDiscoveryRequest {
        val now = System.currentTimeMillis()
        return StrategyDiscoveryRequest
            .newBuilder()
            .setSymbol("BTC/USD")
            .setStartTime(Timestamps.fromMillis(now - 200_000))
            .setEndTime(Timestamps.fromMillis(now - 100_000))
            .setStrategyName("SMA_RSI")
            .setTopN(topN)
            .setGaConfig(
                GAConfig
                    .newBuilder()
                    .setMaxGenerations(10)
                    .setPopulationSize(20)
                    .build(),
            ).build()
    }

    // ----------------------------------------------------------------------
    // Tests
    // ----------------------------------------------------------------------

    @Test
    fun testRunGADiscoveryFn_success() {
        val fn =
            RunGADiscoveryFn(
                StubCandleFetcher(empty = false),
                StubGAEngineFactory(empty = false),
                StubGenotypeConverter(),
            )

        val output: PCollection<StrategyDiscoveryResult> =
            pipeline
                .apply(Create.of(newRequest()))
                .apply(ParDo.of(fn))

        PAssert.that(output).satisfies { iterable ->
            val results = iterable.toList()
            check(results.size == 1) { "Expected 1 result, got ${results.size}" }
            val discovered = results[0].getTopStrategies(0)
            check(discovered.symbol == "BTC/USD")
            check(discovered.strategy.strategyName == "SMA_RSI")
            check(discovered.score >= 0)
            null
        }
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testRunGADiscoveryFn_noCandles() {
        val fn =
            RunGADiscoveryFn(
                StubCandleFetcher(empty = true),
                StubGAEngineFactory(empty = false),
                StubGenotypeConverter(),
            )

        val output =
            pipeline
                .apply(Create.of(newRequest()))
                .apply(ParDo.of(fn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testRunGADiscoveryFn_gaYieldsNoResults() {
        val fn =
            RunGADiscoveryFn(
                StubCandleFetcher(empty = false),
                StubGAEngineFactory(empty = true), // Engine always returns 0 fitness
                StubGenotypeConverter(),
            )

        val output =
            pipeline
                .apply(Create.of(newRequest(topN = 0)))
                .apply(ParDo.of(fn))

        PAssert.that(output).empty()
        pipeline.run().waitUntilFinish()
    }
}

package com.verlumen.tradestream.marketdata // Updated package

import com.google.common.collect.ImmutableList
import com.google.common.truth.Truth.assertThat
import com.google.protobuf.util.Timestamps
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.io.Serializable
import org.apache.beam.sdk.coders.*
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
import org.apache.beam.sdk.testing.PAssert
import org.apache.beam.sdk.testing.TestPipeline
import org.apache.beam.sdk.testing.TestStream
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.windowing.*
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.TimestampedValue
import org.apache.beam.sdk.values.TypeDescriptor
import org.joda.time.Duration
import org.joda.time.Instant
import org.junit.Rule
import org.junit.Test

class CandleLookbackDoFnTest : Serializable { // Make test class serializable

    companion object {
        private const val serialVersionUID = 1L
        private const val TEST_KEY = "BTC/USD"
        // Test with a smaller queue size for manageability
        private const val TEST_MAX_QUEUE_SIZE = 10
    }

    @Rule
    @JvmField
    @Transient // Avoid serialization warnings
    val pipeline: TestPipeline = TestPipeline.create().enableAbandonedNodeEnforcement(true)

    // Helper to create candles
    private fun createCandle(timestampMillis: Long, closePrice: Double): Candle {
        return Candle.newBuilder()
            .setCurrencyPair(TEST_KEY)
            .setTimestamp(Timestamps.fromMillis(timestampMillis))
            .setOpen(closePrice - 1)
            .setHigh(closePrice + 1)
            .setLow(closePrice - 2)
            .setClose(closePrice)
            .setVolume(10.0)
            .build()
    }

    // --- Coders ---
    private val candleCoder: Coder<Candle> = ProtoCoder.of(Candle::class.java)
    private val inputCoder: Coder<KV<String, Candle>> = KvCoder.of(StringUtf8Coder.of(), candleCoder)
    
    // Coder for the immutable list of candles in the output KV value
    private val outputListCoder: Coder<ImmutableList<Candle>> = object : CustomCoder<ImmutableList<Candle>>() {
        private val listCoder: Coder<List<Candle>> = ListCoder.of(candleCoder)
        
        override fun encode(value: ImmutableList<Candle>, outStream: OutputStream) {
            listCoder.encode(ArrayList(value), outStream)
        }

        override fun decode(inStream: InputStream): ImmutableList<Candle> {
            return ImmutableList.copyOf(listCoder.decode(inStream))
        }

        override fun verifyDeterministic() {
            listCoder.verifyDeterministic()
        }
    }
    
    // Coder for the final output structure: KV<String, KV<Int, ImmutableList<Candle>>>
    private val outputCoder: Coder<KV<String, KV<Int, ImmutableList<Candle>>>> = KvCoder.of(
        StringUtf8Coder.of(), KvCoder.of(VarIntCoder.of(), outputListCoder)
    )


    @Test
    fun testLookbackEmission() {
        val baseTimeMillis = 1000L * 60 * 10 // 10 minutes epoch millis
        val intervalMillis = Duration.standardMinutes(1).millis
        val lookbackSizesToTest = listOf(1, 3, 5) // Arbitrary sizes <= queue size

        val testStreamBuilder = TestStream.create(inputCoder)

        // Create 6 candles (less than TEST_MAX_QUEUE_SIZE)
        val candles = (0 until 6).map { i ->
            val time = baseTimeMillis + i * intervalMillis
            KV.of(TEST_KEY, createCandle(time, 100.0 + i))
        }

        var currentTime = Instant(baseTimeMillis)
        var testStream = testStreamBuilder
        for (candleKv in candles) {
            currentTime = Instant(Timestamps.toMillis(candleKv.value.timestamp))
            testStream = testStream.addElements(TimestampedValue.of(candleKv, currentTime))
        }

        // Advance watermark past the elements to trigger the final window
        val finalTime = currentTime.plus(Duration.standardMinutes(5))
        testStream = testStream.advanceWatermarkTo(finalTime)
        // Create final test stream
        val finalTestStream = testStream.advanceWatermarkToInfinity()

        val output = pipeline
            .apply(finalTestStream)
            // Use FixedWindows matching the candle interval for simple testing of state changes
            .apply("ApplyWindow", Window.into<KV<String, Candle>>(
                    FixedWindows.of(Duration.standardMinutes(1)))
                .triggering(AfterWatermark.pastEndOfWindow())
                .withAllowedLateness(Duration.ZERO)
                .discardingFiredPanes()
            )
            // Instantiate DoFn with explicit max size and lookback list
            .apply("CandleLookbacks", ParDo.of(
                CandleLookbackDoFn(TEST_MAX_QUEUE_SIZE, lookbackSizesToTest)
            ))
            .setCoder(outputCoder) // Set output coder

        // Assert results emitted for the *last* window trigger
        PAssert.that(output)
            .satisfies(SerializableFunction<Iterable<KV<String, KV<Int, ImmutableList<Candle>>>>, Void?> { results ->
                val resultsByKey = results.groupBy { it.key }
                val testKeyResults = resultsByKey[TEST_KEY] ?: emptyList()

                val finalCandleTimestamp = Instant(baseTimeMillis + 5 * intervalMillis) // Timestamp of last candle (index 5)

                // Filter for outputs triggered by the last window
                 val finalStateOutputs = testKeyResults.filter {
                     !it.value.value.isEmpty() &&
                     Instant(Timestamps.toMillis(it.value.value.last().timestamp)) == finalCandleTimestamp
                 }

                val emittedLookbackSizes = finalStateOutputs.map { it.value.key }.toSet()

                // Queue size is 6, all requested lookbacks (1, 3, 5) should be present.
                assertThat(emittedLookbackSizes).containsExactlyElementsIn(lookbackSizesToTest.toSet())

                // Check content of lookback size 3 from the final state
                val lookback3Output = finalStateOutputs.find { it.value.key == 3 }
                assertThat(lookback3Output).isNotNull()
                assertThat(lookback3Output!!.value.value).hasSize(3)
                assertThat(lookback3Output.value.value.map { it.close }).containsExactly(103.0, 104.0, 105.0).inOrder()

                 // Check content of lookback size 5 from the final state
                val lookback5Output = finalStateOutputs.find { it.value.key == 5 }
                assertThat(lookback5Output).isNotNull()
                assertThat(lookback5Output!!.value.value).hasSize(5)
                assertThat(lookback5Output.value.value.map { it.close }).containsExactly(101.0, 102.0, 103.0, 104.0, 105.0).inOrder()

                null
            })

        pipeline.run().waitUntilFinish()
    }

    @Test
    fun testQueueBounding() {
        val baseTimeMillis = 1000L * 60 * 10
        val intervalMillis = Duration.standardMinutes(1).millis
        // Request lookbacks up to size 8. Max queue size is 10.
        val lookbackSizesToTest = listOf(1, 3, 5, 8)

        val testStreamBuilder = TestStream.create(inputCoder)
        // Create 15 candles (more than TEST_MAX_QUEUE_SIZE 10)
        val candles = (0 until 15).map { i ->
            val time = baseTimeMillis + i * intervalMillis
            KV.of(TEST_KEY, createCandle(time, 100.0 + i))
        }

        var currentTime = Instant(baseTimeMillis)
        var testStream = testStreamBuilder
        for (candleKv in candles) {
            currentTime = Instant(Timestamps.toMillis(candleKv.value.timestamp))
            testStream = testStream.addElements(TimestampedValue.of(candleKv, currentTime))
        }

        val finalTime = currentTime.plus(Duration.standardMinutes(5))
        testStream = testStream.advanceWatermarkTo(finalTime)
        // Create final test stream
        val finalTestStream = testStream.advanceWatermarkToInfinity()

        val output = pipeline
            .apply(finalTestStream)
            .apply("ApplyWindow", Window.into<KV<String, Candle>>(
                    FixedWindows.of(Duration.standardMinutes(1)))
                .triggering(AfterWatermark.pastEndOfWindow())
                .withAllowedLateness(Duration.ZERO)
                .discardingFiredPanes()
            )
            .apply("CandleLookbacks", ParDo.of(
                CandleLookbackDoFn(TEST_MAX_QUEUE_SIZE, lookbackSizesToTest) // Use TEST_MAX_QUEUE_SIZE
            ))
            .setCoder(outputCoder)

        PAssert.that(output)
             .satisfies(SerializableFunction<Iterable<KV<String, KV<Int, ImmutableList<Candle>>>>, Void?> { results ->
                 val resultsByKey = results.groupBy { it.key }
                 val testKeyResults = resultsByKey[TEST_KEY] ?: emptyList()
                 val finalCandleTimestamp = Instant(baseTimeMillis + 14 * intervalMillis) // Last candle index 14

                 val finalStateOutputs = testKeyResults.filter {
                     !it.value.value.isEmpty() &&
                     Instant(Timestamps.toMillis(it.value.value.last().timestamp)) == finalCandleTimestamp
                 }

                 val emittedLookbackSizes = finalStateOutputs.map { it.value.key }.toSet()

                 // Max queue size is 10. Requested lookbacks are 1, 3, 5, 8. All should be present.
                 val expectedEmittedSizes = setOf(1, 3, 5, 8)
                 assertThat(emittedLookbackSizes).containsExactlyElementsIn(expectedEmittedSizes)

                 // Check the largest emitted size (8)
                 val lookback8Output = finalStateOutputs.find { it.value.key == 8 }
                 assertThat(lookback8Output).isNotNull()
                 assertThat(lookback8Output!!.value.value).hasSize(8)
                 // Queue holds last 10: indices 5..14 (15 candles -> indices 0..14; max size 10 -> keeps 5..14)
                 // Lookback 8 uses indices 7..14 (14 - 8 + 1 = 7)
                 assertThat(Timestamps.toMillis(lookback8Output.value.value.first().timestamp))
                     .isEqualTo(baseTimeMillis + 7 * intervalMillis) // Candle at index 7
                 assertThat(Timestamps.toMillis(lookback8Output.value.value.last().timestamp))
                     .isEqualTo(finalCandleTimestamp.millis) // Candle at index 14

                null
            })

        pipeline.run().waitUntilFinish()
    }
}

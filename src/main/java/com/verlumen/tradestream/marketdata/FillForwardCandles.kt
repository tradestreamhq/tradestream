package com.verlumen.tradestream.marketdata

import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import java.io.Serializable

/**
 * PTransform that applies the FillForwardCandlesFn to fill gaps in a candle stream.
 */
class FillForwardCandles
    @Inject
    constructor(
        @Assisted private val intervalDuration: Duration,
        @Assisted private val maxForwardIntervals: Int = Int.MAX_VALUE,
        private val fillForwardFnFactory: FillForwardCandlesFn.Factory,
    ) : PTransform<PCollection<KV<String, Candle>>, PCollection<KV<String, Candle>>>(), Serializable {
        companion object {
            private const val serialVersionUID = 1L
        }

        override fun expand(input: PCollection<KV<String, Candle>>): PCollection<KV<String, Candle>> {
            // Create the DoFn instance using the injected factory
            val fillForwardFn = fillForwardFnFactory.create(intervalDuration, maxForwardIntervals)
            return input.apply("FillForwardGaps", ParDo.of(fillForwardFn))
        }

        // Factory interface for Guice AssistedInject for this PTransform
        interface Factory {
            fun create(
                intervalDuration: Duration,
                maxForwardIntervals: Int = Int.MAX_VALUE,
            ): FillForwardCandles
        }
    }

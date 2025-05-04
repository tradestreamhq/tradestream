package com.verlumen.tradestream.marketdata

import com.google.inject.Inject
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.transforms.windowing.FixedWindows
import org.apache.beam.sdk.transforms.windowing.Window
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.PDone
import org.apache.beam.sdk.values.TypeDescriptors
import org.joda.time.Duration
import java.util.function.Supplier

/**
 * A PTransform that periodically fetches cryptocurrency candle data from Tiingo
 * for a list of currency pairs.
 */
class TiingoCryptoCandleTransform @Inject constructor(
    private val currencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>,
    private val fetcherFn: TiingoCryptoFetcherFn // Inject the DoFn
) : PTransform<PCollection<Long>, PCollection<Candle>>() { // Input is impulse, output is Candle

    override fun expand(impulse: PCollection<Long>): PCollection<Candle> {
        return impulse
            // Step 2: Get all currency pairs for each impulse
            .apply("GetCurrencyPairs", FlatMapElements
                .into(TypeDescriptor.of(CurrencyPair::class.java))
                .via(SerializableFunction<Long, List<CurrencyPair>> { _ -> currencyPairSupplier.get() })
            )
            // Step 3: Key by currency pair symbol (e.g., "BTC/USD")
            .apply("KeyByCurrencyPair", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.voids()))
                .via(SerializableFunction<CurrencyPair, KV<String, Void>> { pair -> KV.of(pair.symbol(), null as Void?) })
            )
             // Step 4: Group by key to ensure only one fetcher instance per currency pair runs concurrently
             // This also implicitly handles deduplication if the supplier returns duplicates
            .apply("GroupFetchRequests", GroupByKey.create())
            // Step 5: Use the stateful DoFn to fetch candles for each currency pair
            .apply("FetchTiingoCandles", ParDo.of(fetcherFn))
    }

    // Convenience method to apply this transform directly to a pipeline root
    fun expand(pipeline: Pipeline): PCollection<Candle> {
        return pipeline
            // Step 1: Generate an impulse every minute
            .apply("PeriodicImpulse", PeriodicImpulse.create()
                .withInterval(Duration.standardMinutes(1))
                .applyWindowing()) // Apply windowing if needed by PeriodicImpulse
            .apply(this) // Apply the main logic of this transform
    }
}

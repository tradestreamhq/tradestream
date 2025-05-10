package com.verlumen.tradestream.marketdata

import com.google.inject.Inject // Keep for now, will be used by AssistedInject later
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.transforms.FlatMapElements
import org.apache.beam.sdk.transforms.GroupByKey
import org.apache.beam.sdk.transforms.MapElements
import org.apache.beam.sdk.transforms.PTransform
import org.apache.beam.sdk.transforms.ParDo
import org.apache.beam.sdk.transforms.PeriodicImpulse
import org.apache.beam.sdk.transforms.SerializableFunction
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TypeDescriptor
import org.apache.beam.sdk.values.TypeDescriptors
import org.joda.time.Duration
import org.joda.time.Instant
import java.util.function.Supplier

/**
 * A PTransform that periodically fetches cryptocurrency candle data from Tiingo
 * for a list of currency pairs.
 *
 * NOTE: For this PR, the TiingoCryptoFetcherFn is passed directly.
 * In a subsequent PR, this will be replaced by AssistedInject for the transform
 * and its underlying fetcher function to manage granularity and API key configuration.
 */
class TiingoCryptoCandleTransform @Inject constructor( // @Inject will be useful for AssistedInject later
    private val currencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>,
    private val fetcherFn: TiingoCryptoFetcherFn // Temporarily pass the DoFn instance
    // In PR6: private val fetcherFnFactory: TiingoCryptoFetcherFn.Factory,
    // In PR6: @Assisted("granularity") private val granularity: Duration,
    // In PR6: @Assisted("apiKey") private val apiKey: String
) : PTransform<PCollection<Instant>, PCollection<KV<String, Candle>>>() {

    override fun expand(impulse: PCollection<Instant>): PCollection<KV<String, Candle>> {
        // In PR6, fetcherFn would be created here using the factory, granularity, and apiKey
        // val configuredFetcherFn = fetcherFnFactory.create(this.granularity, this.apiKey)

        return impulse
            // Step 2: Get all currency pairs for each impulse
            .apply("GetCurrencyPairs", FlatMapElements
                .into(TypeDescriptor.of(CurrencyPair::class.java))
                .via(SerializableFunction<Instant, List<CurrencyPair>> { _ -> currencyPairSupplier.get() })
            )
            // Step 3: Key by currency pair symbol (e.g., "BTC/USD")
            .apply("KeyByCurrencyPair", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.voids()))
                .via(SerializableFunction<CurrencyPair, KV<String, Void?>> { pair -> KV.of(pair.symbol(), null) })
            )
            // Step 4: Group by key ensures one fetcher instance operates per key if it were stateful across bundles
            // For now, it mainly helps in potential deduplication from supplier.
            .apply("GroupFetchRequests", GroupByKey.create())
            // Step 5: Flatten the grouped data back to individual KVs to match fetcherFn input type
            .apply("UnwrapGroupedPairs", FlatMapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.voids()))
                .via(SerializableFunction<KV<String, Iterable<Void?>>, Iterable<KV<String, Void?>>> { kv ->
                    val key = kv.key
                    listOf(KV.of(key, null))
                })
            )
            // Step 6: Use the stateful DoFn to fetch candles for each currency pair
            .apply("FetchTiingoCandles", ParDo.of(fetcherFn)) // Use the passed fetcherFn
    }

    /**
     * Convenience method to apply this transform directly to a pipeline root,
     * setting up a default PeriodicImpulse.
     *
     * NOTE: The impulse interval and fetcher configuration (granularity, API key)
     * are hardcoded here for now and will be made configurable in PR 6.
     */
    fun expand(pipeline: Pipeline): PCollection<KV<String, Candle>> {
        val defaultImpulseInterval = Duration.standardMinutes(1) // Will be configurable

        return pipeline
            .apply("PeriodicImpulseTrigger", PeriodicImpulse.create()
                .withInterval(defaultImpulseInterval)
                .applyWindowing()) // applyWindowing might be needed depending on Beam version/runner
            .apply("RunTiingoTransform", this)
    }

    // Factory interface will be added in PR 6 for AssistedInject
    // interface Factory {
    //     fun create(
    //         @Assisted("granularity") granularity: Duration,
    //         @Assisted("apiKey") apiKey: String
    //     ): TiingoCryptoCandleTransform
    // }
}

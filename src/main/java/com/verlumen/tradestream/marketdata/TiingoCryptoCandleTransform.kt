package com.verlumen.tradestream.marketdata

import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.transforms.DoFn
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
import java.io.Serializable
import java.util.function.Supplier

/**
 * A PTransform that periodically fetches cryptocurrency candle data from Tiingo
 * for a list of currency pairs.
 *
 * Uses AssistedInject to support configurable granularity and API key.
 */
class TiingoCryptoCandleTransform @Inject constructor(
    private val currencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>,
    private val fetcherFnFactory: TiingoCryptoFetcherFn.Factory,
    @Assisted private val granularity: Duration,
    @Assisted private val apiKey: String
) : PTransform<PCollection<Instant>, PCollection<KV<String, Candle>>>(), Serializable {

    companion object {
        private const val serialVersionUID = 1L
    }

    override fun expand(impulse: PCollection<Instant>): PCollection<KV<String, Candle>> {
        // Get the list of currency pairs once outside the pipeline
        val currencyPairs = currencyPairSupplier.get()
        
        // Create fetcher function with assisted parameters
        val fetcherFn = fetcherFnFactory.create(granularity, apiKey)
        
        return impulse
            // Step 2: Cross with currency pairs from the side input
            .apply("GetCurrencyPairs", FlatMapElements
                .into(TypeDescriptor.of(CurrencyPair::class.java))
                .via(SerializableCurrencyPairFunction(currencyPairs))
            )
            // Step 3: Key by currency pair symbol (e.g., "BTC/USD")
            .apply("KeyByCurrencyPair", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.voids()))
                .via(SerializableFunction<CurrencyPair, KV<String, Void?>> { pair -> 
                    KV.of(pair.symbol(), null) 
                })
            )
            // Step 4: Group by key ensures one fetcher instance operates per key if it were stateful across bundles
            .apply("GroupFetchRequests", GroupByKey.create())
            // Step 5: Flatten the grouped data back to individual KVs
            .apply("UnwrapGroupedPairs", FlatMapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.voids()))
                .via(SerializableFunction<KV<String, Iterable<Void?>>, Iterable<KV<String, Void?>>> { kv ->
                    listOf(KV.of(kv.key, null))
                })
            )
            // Step 6: Use the stateful DoFn to fetch candles for each currency pair
            .apply("FetchTiingoCandles", ParDo.of(fetcherFn))
    }

    /**
     * Convenience method to apply this transform directly to a pipeline root,
     * setting up a PeriodicImpulse with the same granularity.
     */
    fun expand(pipeline: Pipeline): PCollection<KV<String, Candle>> {
        return pipeline
            .apply("PeriodicImpulseTrigger", PeriodicImpulse.create()
                .withInterval(granularity)
                .applyWindowing())
            .apply("RunTiingoTransform", this)
    }
    
    /**
     * Serializable function to transform impulses into currency pairs
     * without capturing external references
     */
    private class SerializableCurrencyPairFunction(
        private val currencyPairs: List<CurrencyPair>
    ) : SerializableFunction<Instant, Iterable<CurrencyPair>>, Serializable {
        companion object {
            private const val serialVersionUID = 1L
        }
        
        override fun apply(input: Instant): Iterable<CurrencyPair> {
            return currencyPairs
        }
    }
    
    /**
     * Factory interface for assisted injection
     */
    interface Factory {
        fun create(granularity: Duration, apiKey: String): TiingoCryptoCandleTransform
    }
}

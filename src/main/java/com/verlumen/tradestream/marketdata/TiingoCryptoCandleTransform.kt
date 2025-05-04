package com.verlumen.tradestream.marketdata

import com.google.inject.assistedinject.Assisted
import com.google.inject.assistedinject.AssistedInject
import com.verlumen.tradestream.instruments.CurrencyPair
import org.apache.beam.sdk.Pipeline
import org.apache.beam.sdk.transforms.*
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PCollection
import org.apache.beam.sdk.values.TypeDescriptors
import org.joda.time.Duration
import java.util.function.Supplier

/**
 * Factory interface for creating TiingoCryptoCandleTransform instances with granularity and API key.
 */
interface TiingoCryptoCandleTransformFactory {
    fun create(
        granularity: Duration,
        apiKey: String
    ): TiingoCryptoCandleTransform
}

/**
 * A PTransform that periodically fetches cryptocurrency candle data from Tiingo.
 */
class TiingoCryptoCandleTransform @AssistedInject constructor(
    private val currencyPairSupplier: Supplier<@JvmSuppressWildcards List<CurrencyPair>>,
    private val fetcherFnFactory: TiingoCryptoFetcherFnFactory,
    @Assisted private val granularity: Duration,
    @Assisted private val apiKey: String
) : PTransform<PCollection<Long>, PCollection<KV<String, Candle>>>() {

    override fun expand(impulse: PCollection<Long>): PCollection<KV<String, Candle>> {
        // Create the DoFn instance using the injected factory and provided config
        val fetcherFn = fetcherFnFactory.create(granularity, apiKey) // Pass apiKey

        return impulse
            .apply("GetCurrencyPairs", FlatMapElements
                .into(TypeDescriptor.of(CurrencyPair::class.java))
                .via(SerializableFunction<Long, List<CurrencyPair>> { _ -> currencyPairSupplier.get() })
            )
            .apply("KeyByCurrencyPair", MapElements
                .into(TypeDescriptors.kvs(TypeDescriptors.strings(), TypeDescriptors.voids()))
                .via(SerializableFunction<CurrencyPair, KV<String, Void>> { pair -> KV.of(pair.symbol(), null as Void?) })
            )
            .apply("GroupFetchRequests", GroupByKey.create())
            .apply("FetchTiingoCandles", ParDo.of(fetcherFn)) // Use the created fetcherFn instance
    }

    // Convenience method to apply this transform directly to a pipeline root
    fun expand(pipeline: Pipeline): PCollection<KV<String, Candle>> {
        return pipeline
            .apply("PeriodicImpulse", PeriodicImpulse.create()
                .withInterval(granularity)
                .applyWindowing())
            .apply(this)
    }

    companion object {
        // Factory interface for Assisted Injection
        interface Factory : TiingoCryptoCandleTransformFactory
    }
}

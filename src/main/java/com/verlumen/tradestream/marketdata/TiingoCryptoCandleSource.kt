package com.verlumen.tradestream.marketdata

import com.google.inject.Inject
import com.google.inject.assistedinject.Assisted
import org.apache.beam.sdk.transforms.PeriodicImpulse
import org.apache.beam.sdk.values.KV
import org.apache.beam.sdk.values.PBegin
import org.apache.beam.sdk.values.PCollection
import org.joda.time.Duration
import java.io.Serializable

/**
 * A CandleSource implementation that uses periodic impulses to trigger
 * Tiingo API calls, fetching cryptocurrency candle data at regular intervals.
 */
class TiingoCryptoCandleSource @Inject constructor( 
    private val transformFactory: TiingoCryptoCandleTransform.Factory,
    @Assisted private val candleInterval: Duration,
    @Assisted private val apiKey: String
) : CandleSource(), Serializable {
    
    companion object {
        private const val serialVersionUID = 1L
    }
    
    override fun expand(input: PBegin): PCollection<KV<String, Candle>> {
        // Create a periodic impulse with the candle interval
        val impulses = input.apply(
            "PeriodicImpulseTrigger", 
            PeriodicImpulse.create()
                .withInterval(candleInterval)
                .applyWindowing()
        )
        
        // Create the transform with the same interval/granularity and API key
        val transform = transformFactory.create(candleInterval, apiKey)
        
        // Apply the transform to fetch candles
        return impulses.apply("FetchTiingoCandles", transform)
    }
    
    /**
     * Factory interface for assisted injection
     */
    interface Factory {
        fun create(candleInterval: Duration, apiKey: String): TiingoCryptoCandleSource
    }
}

package com.verlumen.tradestream.marketdata

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.google.protobuf.util.Timestamps
import org.apache.beam.sdk.coders.SerializableCoder
import org.apache.beam.sdk.state.StateSpec
import org.apache.beam.sdk.state.StateSpecs
import org.apache.beam.sdk.state.TimeDomain
import org.apache.beam.sdk.state.Timer
import org.apache.beam.sdk.state.TimerSpec
import org.apache.beam.sdk.state.TimerSpecs
import org.apache.beam.sdk.state.ValueState
import org.apache.beam.sdk.transforms.DoFn
import org.apache.beam.sdk.transforms.windowing.BoundedWindow
import org.apache.beam.sdk.values.KV
import org.joda.time.Instant
import java.io.Serializable

/**
 * Stateful DoFn that aggregates Trades into a single Candle per key per window.
 */
class CandleCreatorFn @Inject constructor() :
    DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {

    companion object {
        private val logger = FluentLogger.forEnclosingClass()
        private const val serialVersionUID = 1L
        
        private fun candleToString(candle: Candle): String {
             return "Candle{Pair:${candle.currencyPair}, T:${Timestamps.toString(candle.timestamp)}, O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
        }
    }

    @StateId("currentCandle")
    private val currentCandleSpec: StateSpec<ValueState<CandleAccumulator>> =
        StateSpecs.value(SerializableCoder.of(CandleAccumulator::class.java))

    @TimerId("endOfWindowTimer")
    private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)

    @Setup
    fun setup() {
        logger.atInfo().log("Setting up CandleCreatorFn (aggregator only)")
    }

    @ProcessElement
    fun processElement(
        context: ProcessContext,
        @Element element: KV<String, Trade>,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        @TimerId("endOfWindowTimer") timer: Timer,
        window: BoundedWindow
    ) {
        val currencyPair = element.key
        val trade = element.value

        logger.atFine().log("Processing trade for %s: %s in window %s", currencyPair, trade.tradeId, window)

        timer.set(window.maxTimestamp())
        
        processTradeIntoCandle(currencyPair, trade, currentCandleState)
    }

    private fun processTradeIntoCandle(
        currencyPair: String,
        trade: Trade,
        currentCandleState: ValueState<CandleAccumulator>
    ) {
        var accumulator = currentCandleState.read()
    
        if (accumulator == null) {
            // First trade for this key-window
            accumulator = CandleAccumulator()
            accumulator.currencyPair = currencyPair
            accumulator.timestamp = trade.timestamp.seconds
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.initialized = true
            accumulator.isDefault = trade.exchange == "DEFAULT"
            accumulator.firstTradeTimestamp = trade.timestamp.seconds
        } else {
            // Skip default trades if we already have real trades
            if (trade.exchange == "DEFAULT" && !accumulator.isDefault) {
                return
            }

            if (!accumulator.initialized) {
                // First real trade
                accumulator.initialized = true
                accumulator.open = trade.price
                accumulator.high = trade.price
                accumulator.low = trade.price
                accumulator.close = trade.price
                accumulator.volume = trade.volume
                accumulator.isDefault = trade.exchange == "DEFAULT"
                accumulator.firstTradeTimestamp = trade.timestamp.seconds
            } else if (trade.exchange != "DEFAULT") {
                if (accumulator.isDefault) {
                    // First real trade replaces a default
                    accumulator.open = trade.price
                    accumulator.high = trade.price
                    accumulator.low = trade.price
                    accumulator.close = trade.price
                    accumulator.volume = trade.volume
                    accumulator.isDefault = false
                    accumulator.firstTradeTimestamp = trade.timestamp.seconds
                } else {
                    // Check if this is an earlier trade than what we've seen
                    if (trade.timestamp.seconds < accumulator.firstTradeTimestamp) {
                        // This is actually the earliest trade we've seen, use as open
                        accumulator.open = trade.price
                        accumulator.firstTradeTimestamp = trade.timestamp.seconds
                    }
                
                    // Always update high, low, close and volume
                    accumulator.high = maxOf(accumulator.high, trade.price)
                    accumulator.low = minOf(accumulator.low, trade.price)
                    accumulator.close = trade.price
                    accumulator.volume += trade.volume
                }
            }
        }

        currentCandleState.write(accumulator)
    }

    @OnTimer("endOfWindowTimer")
    fun onWindowEnd(
        context: OnTimerContext,
        @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
        window: BoundedWindow
    ) {
        val accumulator = currentCandleState.read()

        if (accumulator != null && accumulator.initialized && !accumulator.isDefault) {
            val candle = buildCandleFromAccumulator(accumulator)
            context.output(KV.of(accumulator.currencyPair, candle))
            logger.atFine().log("Output actual candle for %s at window end %s: %s",
                accumulator.currencyPair, window.maxTimestamp(), candleToString(candle))
        } else {
            val reason = when {
                accumulator == null -> "no accumulator found"
                !accumulator.initialized -> "accumulator not initialized"
                accumulator.isDefault -> "accumulator only contained default trades"
                else -> "unknown reason"
            }
            logger.atFine().log("No actual candle output for key '%s' at window end %s (%s).",
                accumulator?.currencyPair ?: "unknown", window.maxTimestamp(), reason)
        }

        currentCandleState.clear()
    }

    private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
        val builder = Candle.newBuilder()
            .setOpen(acc.open)
            .setHigh(acc.high)
            .setLow(acc.low)
            .setClose(acc.close)
            .setVolume(acc.volume)
            .setCurrencyPair(acc.currencyPair)

        builder.setTimestamp(Timestamps.fromSeconds(acc.timestamp))

        return builder.build()
    }
}

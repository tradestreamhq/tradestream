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
            accumulator = CandleAccumulator()
            accumulator.currencyPair = currencyPair
            accumulator.timestamp = trade.timestamp.seconds
            logger.atFine().log("Created new accumulator for %s with first trade timestamp %d",
                 currencyPair, accumulator.timestamp)
        }

        // Skip default trades if we already have real trades
        if (trade.exchange == "DEFAULT" && !accumulator.isDefault) {
            logger.atFine().log("Skipping default trade - already have real trades")
            return
        }

        if (!accumulator.initialized) {
            // Initialize with first trade (or default trade)
            accumulator.initialized = true
            accumulator.open = trade.price
            accumulator.high = trade.price
            accumulator.low = trade.price
            accumulator.close = trade.price
            accumulator.volume = trade.volume
            accumulator.isDefault = trade.exchange == "DEFAULT"

            logger.atFine().log("Initialized accumulator for %s with %s trade (Price: %.2f, Volume: %.2f)",
                currencyPair, if (accumulator.isDefault) "DEFAULT" else "real", trade.price, trade.volume)
        } else if (trade.exchange != "DEFAULT") {
             // Update with real trade (overwriting default if needed)
             if (accumulator.isDefault) {
                 // First real trade overwrites default completely
                 logger.atFine().log("Overwriting default accumulator with first real trade for %s", currencyPair)
                 accumulator.open = trade.price
                 accumulator.high = trade.price
                 accumulator.low = trade.price
                 accumulator.close = trade.price
                 accumulator.volume = trade.volume
                 accumulator.isDefault = false
                 // Update timestamp to first *real* trade
                 accumulator.timestamp = trade.timestamp.seconds
             } else {
                 // Subsequent real trade updates normally
                 accumulator.high = maxOf(accumulator.high, trade.price)
                 accumulator.low = minOf(accumulator.low, trade.price)
                 accumulator.close = trade.price
                 accumulator.volume += trade.volume
                 // isDefault remains false
             }
            logger.atFine().log("Updated accumulator for %s with real trade, price: %.2f", currencyPair, trade.price)
        }
        // If initialized and trade is DEFAULT, do nothing further

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
            // Simply use output instead of outputWithTimestamp to avoid timestamp skew issues
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

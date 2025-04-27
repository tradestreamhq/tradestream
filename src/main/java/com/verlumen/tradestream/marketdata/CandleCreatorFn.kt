package com.verlumen.tradestream.marketdata
 
 import com.google.common.flogger.FluentLogger
 import com.google.inject.Inject
 import com.google.protobuf.util.Timestamps
 import org.apache.beam.sdk.coders.SerializableCoder
 import org.apache.beam.sdk.extensions.protobuf.ProtoCoder
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
  * When no trades occur in a window, it uses the previous candle's close price to create
  * a continuation candle with zero volume.
  */
 class CandleCreatorFn @Inject constructor() :
     DoFn<KV<String, Trade>, KV<String, Candle>>(), Serializable {
 
     companion object {
         private val logger = FluentLogger.forEnclosingClass()
         private const val serialVersionUID = 1L
 
         private fun candleToString(candle: Candle): String {
             return "Candle{Pair:${candle.currencyPair}, T:${Timestamps.toString(candle.timestamp)}, " +
                    "O:${candle.open}, H:${candle.high}, L:${candle.low}, C:${candle.close}, V:${candle.volume}}"
         }
     }
 
     @StateId("currentCandle")
     private val currentCandleSpec: StateSpec<ValueState<CandleAccumulator>> =
         StateSpecs.value(SerializableCoder.of(CandleAccumulator::class.java))
 
     @StateId("lastEmittedCandle")
     // *** State to remember the last CANDLE FROM ACTUAL TRADES ***
     private val lastCandleSpec: StateSpec<ValueState<Candle>> =
         StateSpecs.value(ProtoCoder.of(Candle::class.java))
 
     @TimerId("endOfWindowTimer")
     private val timerSpec: TimerSpec = TimerSpecs.timer(TimeDomain.EVENT_TIME)
 
     @Setup
     fun setup() {
         logger.atInfo().log("Setting up CandleCreatorFn with fill-forward capability")
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
 
         // Set timer for the end of the window to ensure output even if no more trades arrive
         timer.set(window.maxTimestamp())
 
         processTradeIntoCandle(currencyPair, trade, currentCandleState)
     }
 
     private fun processTradeIntoCandle(
         currencyPair: String,
         trade: Trade,
         currentCandleState: ValueState<CandleAccumulator>
     ) {
         var accumulator = currentCandleState.read()
 
         if (accumulator == null || !accumulator.initialized) {
             // First trade for this key-window
             accumulator = CandleAccumulator()
             accumulator.currencyPair = currencyPair
             accumulator.timestamp = trade.timestamp.seconds // Initialize candle timestamp
             accumulator.open = trade.price
             accumulator.high = trade.price
             accumulator.low = trade.price
             accumulator.close = trade.price
             accumulator.volume = trade.volume
             accumulator.initialized = true
             accumulator.firstTradeTimestamp = trade.timestamp.seconds // Track earliest trade for candle timestamp
             accumulator.latestTradeTimestamp = trade.timestamp.seconds // Track latest trade for close price
         } else {
             // Update based on incoming trade
             if (trade.timestamp.seconds < accumulator.firstTradeTimestamp) {
                 accumulator.open = trade.price
                 accumulator.firstTradeTimestamp = trade.timestamp.seconds
             }
             if (trade.timestamp.seconds >= accumulator.latestTradeTimestamp) {
                 accumulator.close = trade.price
                 accumulator.latestTradeTimestamp = trade.timestamp.seconds
             }
             accumulator.high = maxOf(accumulator.high, trade.price)
             accumulator.low = minOf(accumulator.low, trade.price)
             accumulator.volume += trade.volume
         }
 
         currentCandleState.write(accumulator)
     }
 
     @OnTimer("endOfWindowTimer")
     fun onWindowEnd(
         context: OnTimerContext,
         @StateId("currentCandle") currentCandleState: ValueState<CandleAccumulator>,
         @StateId("lastEmittedCandle") lastCandleState: ValueState<Candle>, // Reads the last ACTUAL candle
         window: BoundedWindow
     ) {
         val accumulator = currentCandleState.read()
         val lastActualCandleFromState = lastCandleState.read() // Renamed for clarity
 
         val key = when {
             accumulator != null && accumulator.initialized -> accumulator.currencyPair
             lastActualCandleFromState != null -> lastActualCandleFromState.currencyPair
             else -> {
                 logger.atFine().log("No key found for window %s, cannot output.", window.maxTimestamp())
                 currentCandleState.clear()
                 // lastCandleState.clear() // Optional: Clear if no history desired after long gap
                 return
             }
         }
 
         val candleToOutput: Candle?
 
         if (accumulator != null && accumulator.initialized) {
             // *** Case 1: Trades occurred in this window ***
             val actualCandle = buildCandleFromAccumulator(accumulator)
             candleToOutput = actualCandle
             // *** CRITICAL FIX 1: Only write ACTUAL candles to lastCandleState ***
             lastCandleState.write(actualCandle)
             logger.atFine().log(
                 "Output actual candle for %s at window end %s: %s",
                 key, window.maxTimestamp(), candleToString(actualCandle)
             )
         } else if (lastActualCandleFromState != null) {
             // *** Case 2: No trades, but we have a previous ACTUAL candle state ***
             val fillForwardCandle = buildFillForwardCandle(key, lastActualCandleFromState, window.maxTimestamp())
             candleToOutput = fillForwardCandle
             // *** CRITICAL FIX 2: DO NOT write the fill-forward candle back to lastCandleState ***
             // The state correctly retains the last *actual* candle data.
             logger.atFine().log(
                 "Output fill-forward candle for %s at window end %s: %s (based on last actual close: ${lastActualCandleFromState.close})",
                 key, window.maxTimestamp(), candleToString(fillForwardCandle)
             )
         } else {
             // *** Case 3: No trades and no prior actual candle history for this key ***
             candleToOutput = null
             lastCandleState.clear() // Clear state as there's no history
             logger.atFine().log(
                 "No candle output for key '%s' at window end %s (no trades and no prior candle).",
                 key, window.maxTimestamp()
             )
         }
 
         // Output the determined candle (if any)
         candleToOutput?.let {
             context.outputWithTimestamp(KV.of(key, it), window.maxTimestamp())
         }
 
         // Always clear the trade accumulator for the processed window
         currentCandleState.clear()
     }
 
     // Helper to build candle from accumulator data
     private fun buildCandleFromAccumulator(acc: CandleAccumulator): Candle {
         val builder = Candle.newBuilder()
             .setOpen(acc.open)
             .setHigh(acc.high)
             .setLow(acc.low)
             .setClose(acc.close)
             .setVolume(acc.volume)
             .setCurrencyPair(acc.currencyPair)
         // Use the first trade timestamp for the candle timestamp
         builder.setTimestamp(Timestamps.fromSeconds(acc.firstTradeTimestamp))
         return builder.build()
     }
 
     // Helper to build a fill-forward candle
     private fun buildFillForwardCandle(key: String, lastActualCandle: Candle, windowEnd: Instant): Candle {
         return Candle.newBuilder()
             .setCurrencyPair(key)
             .setTimestamp(Timestamps.fromMillis(windowEnd.millis)) // Timestamp is the end of the empty window
             .setOpen(lastActualCandle.close)  // Use last actual close price
             .setHigh(lastActualCandle.close)
             .setLow(lastActualCandle.close)
             .setClose(lastActualCandle.close)
             .setVolume(0.0) // Zero volume indicates fill-forward
             .build()
     }
 }

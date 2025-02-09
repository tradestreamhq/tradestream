package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.google.common.flogger.FluentLogger;  // <-- Added FluentLogger import
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.Trade;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.IOException;
import org.apache.beam.sdk.coders.*;
import org.apache.beam.sdk.extensions.protobuf.ProtoCoder;
import org.apache.beam.sdk.transforms.Combine;
import org.apache.beam.sdk.transforms.PTransform;
import org.apache.beam.sdk.transforms.windowing.SlidingWindows;
import org.apache.beam.sdk.transforms.windowing.Window;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Duration;

/**
 * SlidingCandleAggregator aggregates Trade messages into a Candle per sliding window.
 * The input is a PCollection of KV<String, Trade> keyed by currency pair (e.g. "BTC/USD").
 */
public class SlidingCandleAggregator
        extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, Candle>>> {

    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    private static final double ZERO = 0.0;

    private final Duration windowDuration;
    private final Duration slideDuration;

    public SlidingCandleAggregator(Duration windowDuration, Duration slideDuration) {
        this.windowDuration = windowDuration;
        this.slideDuration = slideDuration;
    }

    @Override
    public PCollection<KV<String, Candle>> expand(PCollection<KV<String, Trade>> input) {
        logger.atInfo().log(
            "Starting SlidingCandleAggregator. WindowDuration=%s, SlideDuration=%s, Input=%s",
            windowDuration, slideDuration, input
        );

        // Apply sliding window.
        PCollection<KV<String, Trade>> windowed = input.apply(
            "ApplySlidingWindow",
            Window.<KV<String, Trade>>into(SlidingWindows.of(windowDuration).every(slideDuration))
        );
        logger.atFine().log("Applied sliding window. Output PCollection: %s", windowed);

        // Aggregate trades into Candles per key.
        PCollection<KV<String, Candle>> output = windowed.apply(
            "AggregateToCandle",
            Combine.perKey(new CandleCombineFn())
        );
        logger.atFine().log("Applied Combine.perKey with CandleCombineFn. Output PCollection: %s", output);

        // Set coder for the output.
        output.setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle.class)));
        logger.atInfo().log("Set KvCoder on output. Final output coder: %s", output.getCoder());

        logger.atInfo().log("Finished SlidingCandleAggregator. Returning output: %s", output);
        return output;
    }

    /**
     * CandleCombineFn aggregates Trade messages into a Candle.
     */
    public static class CandleCombineFn extends Combine.CombineFn<Trade, CandleAccumulator, Candle> {
        private static final FluentLogger logger = FluentLogger.forEnclosingClass();

        @Override
        public Coder<CandleAccumulator> getAccumulatorCoder(CoderRegistry registry, Coder<Trade> inputCoder) {
            logger.atFine().log("getAccumulatorCoder called for CandleCombineFn.");
            return new CandleAccumulatorCoder();
        }

        @Override
        public CandleAccumulator createAccumulator() {
            CandleAccumulator accumulator = new CandleAccumulator();
            logger.atFine().log("Created new CandleAccumulator: %s", accumulator);
            return accumulator;
        }

        @Override
        public CandleAccumulator addInput(CandleAccumulator accumulator, Trade trade) {
            logger.atFiner().log("Adding input trade %s to accumulator: %s", trade, accumulator);

            // If the trade is synthetic (i.e. "DEFAULT"), ignore if we already have a real trade.
            if ("DEFAULT".equals(trade.getExchange())) {
                if (!accumulator.firstTrade) {
                    logger.atFiner().log("Synthetic trade ignored. Accumulator already has a real trade.");
                }
                return accumulator;
            }

            // Process a real trade.
            if (accumulator.firstTrade) {
                // First trade initializes the accumulator.
                accumulator.open = trade.getPrice();
                accumulator.high = trade.getPrice();
                accumulator.low = trade.getPrice();
                accumulator.close = trade.getPrice();
                accumulator.volume = trade.getVolume();
                accumulator.openTimestamp = trade.getTimestamp();
                accumulator.closeTimestamp = trade.getTimestamp();
                accumulator.currencyPair = trade.getCurrencyPair();
                accumulator.firstTrade = false;
                logger.atFiner().log("Initialized accumulator with first real trade. Accumulator now: %s", accumulator);
            } else {
                // Update high, low, and volume.
                accumulator.high = Math.max(accumulator.high, trade.getPrice());
                accumulator.low = Math.min(accumulator.low, trade.getPrice());
                accumulator.volume += trade.getVolume();

                // Update open/close if needed.
                if (trade.getTimestamp().getSeconds() < accumulator.openTimestamp.getSeconds()) {
                    accumulator.open = trade.getPrice();
                    accumulator.openTimestamp = trade.getTimestamp();
                }
                if (trade.getTimestamp().getSeconds() > accumulator.closeTimestamp.getSeconds()) {
                    accumulator.close = trade.getPrice();
                    accumulator.closeTimestamp = trade.getTimestamp();
                }
                logger.atFiner().log("Updated accumulator with real trade. Accumulator now: %s", accumulator);
            }
            return accumulator;
        }

        @Override
        public CandleAccumulator mergeAccumulators(Iterable<CandleAccumulator> accumulators) {
            logger.atFine().log("Merging accumulators in CandleCombineFn.");
            CandleAccumulator merged = createAccumulator();

            for (CandleAccumulator acc : accumulators) {
                logger.atFiner().log("Merging accumulator: %s into: %s", acc, merged);
                if (acc.firstTrade) {
                    // This accumulator has no real trades, skip it.
                    continue;
                }
                if (merged.firstTrade) {
                    // Copy the first non-empty accumulator.
                    merged.open = acc.open;
                    merged.high = acc.high;
                    merged.low = acc.low;
                    merged.close = acc.close;
                    merged.volume = acc.volume;
                    merged.openTimestamp = acc.openTimestamp;
                    merged.closeTimestamp = acc.closeTimestamp;
                    merged.currencyPair = acc.currencyPair;
                    merged.firstTrade = false;
                } else {
                    // Merge logic for subsequent accumulators.
                    if (acc.openTimestamp.getSeconds() < merged.openTimestamp.getSeconds()) {
                        merged.open = acc.open;
                        merged.openTimestamp = acc.openTimestamp;
                    }
                    if (acc.closeTimestamp.getSeconds() > merged.closeTimestamp.getSeconds()) {
                        merged.close = acc.close;
                        merged.closeTimestamp = acc.closeTimestamp;
                    }
                    merged.high = Math.max(merged.high, acc.high);
                    merged.low = Math.min(merged.low, acc.low);
                    merged.volume += acc.volume;
                }
                logger.atFiner().log("Post-merge state: %s", merged);
            }
            logger.atFine().log("Finished merging accumulators. Final merged: %s", merged);
            return merged;
        }

        @Override
        public Candle extractOutput(CandleAccumulator accumulator) {
            logger.atFiner().log("Extracting Candle from accumulator: %s", accumulator);
            Candle.Builder builder = Candle.newBuilder();
            if (accumulator.firstTrade) {
                // No trades were added. Produce a default candle.
                builder.setOpen(ZERO)
                       .setHigh(ZERO)
                       .setLow(ZERO)
                       .setClose(ZERO)
                       .setVolume(ZERO)
                       .setTimestamp(Timestamp.getDefaultInstance());
                logger.atFiner().log("No real trades found. Returning default Candle.");
            } else {
                builder.setOpen(accumulator.open)
                       .setHigh(accumulator.high)
                       .setLow(accumulator.low)
                       .setClose(accumulator.close)
                       .setVolume(accumulator.volume)
                       // Use the openTimestamp as the candle’s representative timestamp.
                       .setTimestamp(accumulator.openTimestamp)
                       .setCurrencyPair(accumulator.currencyPair);
                logger.atFiner().log("Returning real Candle from accumulator.");
            }
            Candle result = builder.build();
            logger.atFiner().log("Final Candle output: %s", result);
            return result;
        }
    }

    /**
     * CandleAccumulator holds the intermediate aggregation state.
     */
    public static class CandleAccumulator {
        double open = ZERO;
        double high = ZERO;
        double low = ZERO;
        double close = ZERO;
        double volume = ZERO;

        // Track both the earliest (open) and latest (close) timestamps.
        Timestamp openTimestamp;
        Timestamp closeTimestamp;
        String currencyPair;
        boolean firstTrade = true;

        @Override
        public String toString() {
            return String.format(
                "CandleAccumulator{open=%.4f, high=%.4f, low=%.4f, close=%.4f, volume=%.4f, firstTrade=%b, openTs=%s, closeTs=%s, pair=%s}",
                open, high, low, close, volume, firstTrade,
                openTimestamp, closeTimestamp, currencyPair
            );
        }
    }

    /**
     * Custom coder for CandleAccumulator to enable serialization/deserialization in the Beam pipeline.
     */
    private static class CandleAccumulatorCoder extends CustomCoder<CandleAccumulator> {
        private static final FluentLogger logger = FluentLogger.forEnclosingClass();

        private static final Coder<Double> DOUBLE_CODER = DoubleCoder.of();
        private static final Coder<Boolean> BOOLEAN_CODER = BooleanCoder.of();
        private static final Coder<String> STRING_CODER = StringUtf8Coder.of();
        private static final Coder<Timestamp> TIMESTAMP_CODER = ProtoCoder.of(Timestamp.class);

        @Override
        public void encode(CandleAccumulator value, OutputStream outStream) throws IOException {
            logger.atFinest().log("Encoding CandleAccumulator: %s", value);
            DOUBLE_CODER.encode(value.open, outStream);
            DOUBLE_CODER.encode(value.high, outStream);
            DOUBLE_CODER.encode(value.low, outStream);
            DOUBLE_CODER.encode(value.close, outStream);
            DOUBLE_CODER.encode(value.volume, outStream);
            BOOLEAN_CODER.encode(value.firstTrade, outStream);

            // Encode openTimestamp
            boolean hasOpenTimestamp = value.openTimestamp != null;
            BOOLEAN_CODER.encode(hasOpenTimestamp, outStream);
            if (hasOpenTimestamp) {
                TIMESTAMP_CODER.encode(value.openTimestamp, outStream);
            }

            // Encode closeTimestamp
            boolean hasCloseTimestamp = value.closeTimestamp != null;
            BOOLEAN_CODER.encode(hasCloseTimestamp, outStream);
            if (hasCloseTimestamp) {
                TIMESTAMP_CODER.encode(value.closeTimestamp, outStream);
            }

            // Encode currencyPair
            boolean hasCurrencyPair = value.currencyPair != null;
            BOOLEAN_CODER.encode(hasCurrencyPair, outStream);
            if (hasCurrencyPair) {
                STRING_CODER.encode(value.currencyPair, outStream);
            }
            logger.atFinest().log("Finished encoding CandleAccumulator.");
        }

        @Override
        public CandleAccumulator decode(InputStream inStream) throws IOException {
            CandleAccumulator acc = new CandleAccumulator();
            acc.open = DOUBLE_CODER.decode(inStream);
            acc.high = DOUBLE_CODER.decode(inStream);
            acc.low = DOUBLE_CODER.decode(inStream);
            acc.close = DOUBLE_CODER.decode(inStream);
            acc.volume = DOUBLE_CODER.decode(inStream);
            acc.firstTrade = BOOLEAN_CODER.decode(inStream);

            boolean hasOpenTimestamp = BOOLEAN_CODER.decode(inStream);
            if (hasOpenTimestamp) {
                acc.openTimestamp = TIMESTAMP_CODER.decode(inStream);
            }

            boolean hasCloseTimestamp = BOOLEAN_CODER.decode(inStream);
            if (hasCloseTimestamp) {
                acc.closeTimestamp = TIMESTAMP_CODER.decode(inStream);
            }

            boolean hasCurrencyPair = BOOLEAN_CODER.decode(inStream);
            if (hasCurrencyPair) {
                acc.currencyPair = STRING_CODER.decode(inStream);
            }
            logger.atFinest().log("Decoded CandleAccumulator: %s", acc);
            return acc;
        }
    }
}

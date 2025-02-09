package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
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

    private static final double ZERO = 0.0;
    private final Duration windowDuration;
    private final Duration slideDuration;

    public SlidingCandleAggregator(Duration windowDuration, Duration slideDuration) {
        this.windowDuration = windowDuration;
        this.slideDuration = slideDuration;
    }

    @Override
    public PCollection<KV<String, Candle>> expand(PCollection<KV<String, Trade>> input) {
        PCollection<KV<String, Candle>> output = input
                .apply(Window.into(SlidingWindows.of(windowDuration).every(slideDuration)))
                .apply("AggregateToCandle", Combine.perKey(new CandleCombineFn()));

        output.setCoder(KvCoder.of(StringUtf8Coder.of(), ProtoCoder.of(Candle.class)));
        return output;
    }

    /**
     * CandleCombineFn aggregates Trade messages into a Candle.
     */
    public static class CandleCombineFn extends Combine.CombineFn<Trade, CandleAccumulator, Candle> {

        @Override
        public Coder<CandleAccumulator> getAccumulatorCoder(CoderRegistry registry, Coder<Trade> inputCoder) {
            return new CandleAccumulatorCoder();
        }

        @Override
        public CandleAccumulator createAccumulator() {
            return new CandleAccumulator();
        }

        @Override
        public CandleAccumulator addInput(CandleAccumulator accumulator, Trade trade) {
            // If the trade is synthetic (i.e. default) then ignore it if a real trade is already present.
            if ("DEFAULT".equals(trade.getExchange())) {
                // If we already have a real trade, do not update the accumulator.
                if (!accumulator.firstTrade) {
                    return accumulator;
                }
                // If no real trade is present, do not initialize the accumulator.
                return accumulator;
            }

            // Process a real trade normally.
            if (accumulator.firstTrade) {
                // First trade initializes the accumulator.
                accumulator.open = trade.getPrice();
                accumulator.high = trade.getPrice();
                accumulator.low = trade.getPrice();
                accumulator.close = trade.getPrice();
                accumulator.volume = trade.getVolume();
                accumulator.openTimestamp = trade.getTimestamp();
                accumulator.closeTimestamp = trade.getTimestamp();
                accumulator.currencyPair = trade.getCurrencyPair();  // Assumed to be a String in this version.
                accumulator.firstTrade = false;
            } else {
                // Update high, low, and volume.
                accumulator.high = Math.max(accumulator.high, trade.getPrice());
                accumulator.low = Math.min(accumulator.low, trade.getPrice());
                accumulator.volume += trade.getVolume();

                // Update open if this trade is earlier.
                if (trade.getTimestamp().getSeconds() < accumulator.openTimestamp.getSeconds()) {
                    accumulator.open = trade.getPrice();
                    accumulator.openTimestamp = trade.getTimestamp();
                }
                // Update close if this trade is later.
                if (trade.getTimestamp().getSeconds() > accumulator.closeTimestamp.getSeconds()) {
                    accumulator.close = trade.getPrice();
                    accumulator.closeTimestamp = trade.getTimestamp();
                }
            }
            return accumulator;
        }

        @Override
        public CandleAccumulator mergeAccumulators(Iterable<CandleAccumulator> accumulators) {
            CandleAccumulator merged = createAccumulator();
            for (CandleAccumulator acc : accumulators) {
                if (acc.firstTrade) {
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
                    // Update open: choose the earliest trade.
                    if (acc.openTimestamp.getSeconds() < merged.openTimestamp.getSeconds()) {
                        merged.open = acc.open;
                        merged.openTimestamp = acc.openTimestamp;
                    }
                    // Update close: choose the latest trade.
                    if (acc.closeTimestamp.getSeconds() > merged.closeTimestamp.getSeconds()) {
                        merged.close = acc.close;
                        merged.closeTimestamp = acc.closeTimestamp;
                    }
                    // Update high, low, and volume.
                    merged.high = Math.max(merged.high, acc.high);
                    merged.low = Math.min(merged.low, acc.low);
                    merged.volume += acc.volume;
                }
            }
            return merged;
        }

        @Override
        public Candle extractOutput(CandleAccumulator accumulator) {
            Candle.Builder builder = Candle.newBuilder();
            if (accumulator.firstTrade) {
                // No trades were added. Produce a default candle.
                builder.setOpen(ZERO)
                       .setHigh(ZERO)
                       .setLow(ZERO)
                       .setClose(ZERO)
                       .setVolume(ZERO)
                       .setTimestamp(Timestamp.getDefaultInstance());
            } else {
                builder.setOpen(accumulator.open)
                       .setHigh(accumulator.high)
                       .setLow(accumulator.low)
                       .setClose(accumulator.close)
                       .setVolume(accumulator.volume)
                       // Here we use the openTimestamp as the candle’s timestamp.
                       .setTimestamp(accumulator.openTimestamp)
                       .setCurrencyPair(accumulator.currencyPair);
            }
            return builder.build();
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
    }

    /**
     * Custom coder for CandleAccumulator to enable serialization/deserialization in the Beam pipeline.
     */
    private static class CandleAccumulatorCoder extends CustomCoder<CandleAccumulator> {
        private static final Coder<Double> DOUBLE_CODER = DoubleCoder.of();
        private static final Coder<Boolean> BOOLEAN_CODER = BooleanCoder.of();
        private static final Coder<String> STRING_CODER = StringUtf8Coder.of();
        private static final Coder<Timestamp> TIMESTAMP_CODER = ProtoCoder.of(Timestamp.class);

        @Override
        public void encode(CandleAccumulator value, OutputStream outStream) throws IOException {
            DOUBLE_CODER.encode(value.open, outStream);
            DOUBLE_CODER.encode(value.high, outStream);
            DOUBLE_CODER.encode(value.low, outStream);
            DOUBLE_CODER.encode(value.close, outStream);
            DOUBLE_CODER.encode(value.volume, outStream);
            BOOLEAN_CODER.encode(value.firstTrade, outStream);

            // Encode the openTimestamp.
            boolean hasOpenTimestamp = value.openTimestamp != null;
            BOOLEAN_CODER.encode(hasOpenTimestamp, outStream);
            if (hasOpenTimestamp) {
                TIMESTAMP_CODER.encode(value.openTimestamp, outStream);
            }

            // Encode the closeTimestamp.
            boolean hasCloseTimestamp = value.closeTimestamp != null;
            BOOLEAN_CODER.encode(hasCloseTimestamp, outStream);
            if (hasCloseTimestamp) {
                TIMESTAMP_CODER.encode(value.closeTimestamp, outStream);
            }

            // Encode the currencyPair.
            boolean hasCurrencyPair = value.currencyPair != null;
            BOOLEAN_CODER.encode(hasCurrencyPair, outStream);
            if (hasCurrencyPair) {
                STRING_CODER.encode(value.currencyPair, outStream);
            }
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

            return acc;
        }
    }
}

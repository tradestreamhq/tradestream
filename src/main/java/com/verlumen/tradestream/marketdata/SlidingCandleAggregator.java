package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.Trade;
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
public class SlidingCandleAggregator extends PTransform<PCollection<KV<String, Trade>>, PCollection<KV<String, Candle>>> {
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

        // Rest of CandleCombineFn implementation remains the same
        @Override
        public CandleAccumulator createAccumulator() {
            return new CandleAccumulator();
        }

        @Override
        public CandleAccumulator addInput(CandleAccumulator accumulator, Trade trade) {
            if (accumulator.firstTrade) {
                accumulator.open = trade.getPrice();
                accumulator.high = trade.getPrice();
                accumulator.low = trade.getPrice();
                accumulator.close = trade.getPrice();
                accumulator.volume = trade.getVolume();
                accumulator.timestamp = trade.getTimestamp();
                accumulator.currencyPair = trade.getCurrencyPair();
                accumulator.firstTrade = false;
            } else {
                accumulator.high = Math.max(accumulator.high, trade.getPrice());
                accumulator.low = Math.min(accumulator.low, trade.getPrice());
                accumulator.close = trade.getPrice();
                accumulator.volume += trade.getVolume();
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
                    merged.open = acc.open;
                    merged.high = acc.high;
                    merged.low = acc.low;
                    merged.close = acc.close;
                    merged.volume = acc.volume;
                    merged.timestamp = acc.timestamp;
                    merged.currencyPair = acc.currencyPair;
                    merged.firstTrade = false;
                } else {
                    if (acc.timestamp.getSeconds() < merged.timestamp.getSeconds()) {
                        merged.open = acc.open;
                        merged.timestamp = acc.timestamp;
                    }
                    merged.high = Math.max(merged.high, acc.high);
                    merged.low = Math.min(merged.low, acc.low);
                    merged.close = acc.close;
                    merged.volume += acc.volume;
                }
            }
            return merged;
        }

        @Override
        public Candle extractOutput(CandleAccumulator accumulator) {
            Candle.Builder builder = Candle.newBuilder();
            if (accumulator.firstTrade) {
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
                       .setTimestamp(accumulator.timestamp)
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
        Timestamp timestamp;
        String currencyPair;
        boolean firstTrade = true;
    }

    /**
     * Custom coder for CandleAccumulator to enable serialization/deserialization in Beam pipeline.
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
            
            // Handle nullable fields
            boolean hasTimestamp = value.timestamp != null;
            BOOLEAN_CODER.encode(hasTimestamp, outStream);
            if (hasTimestamp) {
                TIMESTAMP_CODER.encode(value.timestamp, outStream);
            }
            
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
            
            boolean hasTimestamp = BOOLEAN_CODER.decode(inStream);
            if (hasTimestamp) {
                acc.timestamp = TIMESTAMP_CODER.decode(inStream);
            }
            
            boolean hasCurrencyPair = BOOLEAN_CODER.decode(inStream);
            if (hasCurrencyPair) {
                acc.currencyPair = STRING_CODER.decode(inStream);
            }
            
            return acc;
        }
    }
}

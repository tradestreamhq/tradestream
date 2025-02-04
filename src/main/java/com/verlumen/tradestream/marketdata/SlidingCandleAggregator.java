package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.verlumen.tradestream.marketdata.Candle;
import com.verlumen.tradestream.marketdata.Trade;
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
        return input
                .apply(Window.into(SlidingWindows.of(windowDuration).every(slideDuration)))
                .apply("AggregateToCandle", Combine.perKey(new CandleCombineFn()));
    }

    /**
     * CandleCombineFn aggregates Trade messages into a Candle.
     */
    public static class CandleCombineFn extends Combine.CombineFn<Trade, CandleAccumulator, Candle> {

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
                accumulator.currencyPair = trade.getCurrencyPair(); // Trade returns String directly
                accumulator.firstTrade = false;
            } else {
                // Use direct numeric comparisons instead of object methods
                accumulator.high = Math.max(accumulator.high, trade.getPrice());
                accumulator.low = Math.min(accumulator.low, trade.getPrice());
                accumulator.close = trade.getPrice();
                accumulator.volume += trade.getVolume(); // Use addition operator
            }
            return accumulator;
        }

        @Override 
        public CandleAccumulator mergeAccumulators(CandleAccumulator merged, CandleAccumulator acc) {
            if (acc.firstTrade) {
                return merged;
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
                // Use timestamp comparison for oldest open
                if (acc.timestamp.getSeconds() < merged.timestamp.getSeconds()) {
                    merged.open = acc.open;
                    merged.timestamp = acc.timestamp;
                }
                merged.high = Math.max(merged.high, acc.high);
                merged.low = Math.min(merged.low, acc.low);
                merged.close = acc.close;
                merged.volume += acc.volume; // Use addition operator
            }
            return merged;
        }

        @Override
        public Candle extractOutput(CandleAccumulator accumulator) {
            Candle.Builder builder = Candle.newBuilder();
            if (accumulator.firstTrade) {
                // No trade was received; produce a default candle.
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

        private int compareTimestamps(Timestamp t1, Timestamp t2) {
            return Long.compare(t1.getSeconds(), t2.getSeconds());
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
}

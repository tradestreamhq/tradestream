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
                // Create a string like "BTC/USD"
                accumulator.currencyPair = trade.getCurrencyPair().getBase() + "/" + trade.getCurrencyPair().getQuote();
                accumulator.firstTrade = false;
            } else {
                accumulator.high = accumulator.high.max(trade.getPrice());
                accumulator.low = accumulator.low.min(trade.getPrice());
                accumulator.close = trade.getPrice();
                accumulator.volume = accumulator.volume.add(trade.getVolume());
            }
            return accumulator;
        }

        @Override
        public CandleAccumulator mergeAccumulators(Iterable<CandleAccumulator> accumulators) {
            CandleAccumulator merged = createAccumulator();
            boolean first = true;
            for (CandleAccumulator acc : accumulators) {
                if (acc.firstTrade) continue;
                if (first) {
                    merged.open = acc.open;
                    merged.high = acc.high;
                    merged.low = acc.low;
                    merged.close = acc.close;
                    merged.volume = acc.volume;
                    merged.timestamp = acc.timestamp;
                    merged.currencyPair = acc.currencyPair;
                    first = false;
                } else {
                    if (compareTimestamps(acc.timestamp, merged.timestamp) < 0) {
                        merged.open = acc.open;
                        merged.timestamp = acc.timestamp;
                    }
                    merged.high = merged.high.max(acc.high);
                    merged.low = merged.low.min(acc.low);
                    merged.close = acc.close;
                    merged.volume = merged.volume.add(acc.volume);
                }
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

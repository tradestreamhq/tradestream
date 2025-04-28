package com.verlumen.tradestream.marketdata;

import com.google.protobuf.Timestamp;
import com.google.common.flogger.FluentLogger;
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

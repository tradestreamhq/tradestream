package com.verlumen.tradestream.marketdata;

import com.google.protobuf.util.Timestamps;
import com.google.inject.Inject;
import org.apache.beam.sdk.transforms.WithTimestamps;
import org.apache.beam.sdk.values.KV;
import org.apache.beam.sdk.values.PBegin;
import org.apache.beam.sdk.values.PCollection;
import org.joda.time.Instant;

/**
 * A CandleSource implementation that creates candles from trade data.
 * This implementation reads trades from a source, assigns timestamps, 
 * and converts them to candles.
 */
public class TradeBackedCandleSource extends CandleSource {
    
    private final TradeSource tradeSource;
    private final TradeToCandle tradeToCandle;
    
    @Inject
    public TradeBackedCandleSource(TradeSource tradeSource, TradeToCandle tradeToCandle) {
        this.tradeSource = tradeSource;
        this.tradeToCandle = tradeToCandle;
    }
    
    @Override
    public PCollection<KV<String, Candle>> expand(PBegin input) {
        // 1. Read trades from the source
        PCollection<Trade> trades = input.apply("ReadTrades", tradeSource);
        
        // 2. Assign timestamps from the Trade's own timestamp
        PCollection<Trade> tradesWithTimestamps = trades.apply(
            "AssignTimestamps",
            WithTimestamps.<Trade>of(
                trade -> {
                    long millis = Timestamps.toMillis(trade.getTimestamp());
                    return new Instant(millis);
                }
            )
        );
        
        // 3. Create candles from trades
        return tradesWithTimestamps.apply("CreateCandles", tradeToCandle);
    }
}

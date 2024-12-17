package com.verlumen.tradestream.strategies.dataconsumption;

import com.google.auto.value.AutoValue;
import com.google.common.collect.ImmutableList;
import com.google.common.collect.ImmutableMap;
import com.google.common.flogger.FluentLogger;
import com.google.inject.Inject;
import com.verlumen.tradestream.marketdata.Candle;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;

import java.time.Duration;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.TimeUnit;

/**
 * Maintains a sliding window of candles for a specific timeframe.
 */
final class CandleWindowImpl implements CandleWindow {
    private final List<Candle> candles = Collections.synchronizedList(new ArrayList<>());
    private final Duration timeframe;

    CandleWindowImpl(Duration timeframe) {
        this.timeframe = timeframe;
    }

    void addCandle(Candle candle) {
        candles.add(candle);
    }

    List<Candle> getCandles(int windowSize) {
        synchronized (candles) {
            int fromIndex = Math.max(0, candles.size() - windowSize);
            return ImmutableList.copyOf(candles.subList(fromIndex, candles.size()));
        }
    }
}

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

final class DataConsumptionLayerImpl implements DataConsumptionLayer {
    private static final FluentLogger logger = FluentLogger.forEnclosingClass();
    
    // Maps currency pair to timeframe to candle window
    private final Map<String, Map<Duration, CandleWindow>> windowsByPairAndTimeframe;
    private final ImmutableList<Duration> supportedTimeframes;
    private final Duration baseCandleTimeframe;
    private final KafkaConsumer<String, byte[]> consumer;

    @Inject
    DataConsumptionLayerImpl(Config config) {
        logger.atInfo().log("Initializing DataConsumptionLayer");
        
        this.windowsByPairAndTimeframe = new ConcurrentHashMap<>();
        this.supportedTimeframes = ImmutableList.copyOf(config.getSupportedTimeframes());
        this.baseCandleTimeframe = config.getBaseCandleTimeframe();
        
        Properties props = new Properties();
        props.put("bootstrap.servers", config.getKafkaBootstrapServers());
        props.put("group.id", "strategy-consumer");
        props.put("key.deserializer", "org.apache.kafka.common.serialization.StringDeserializer");
        props.put("value.deserializer", "org.apache.kafka.common.serialization.ByteArrayDeserializer");
        
        this.consumer = new KafkaConsumer<>(props);
        consumer.subscribe(Collections.singletonList(config.getKafkaTopic()));
        
        logger.atInfo().log("DataConsumptionLayer initialization complete");
    }

    @Override
    public void consumeCandle(Candle candle) {
        logger.atInfo().log("Processing new candle for %s", candle.getCurrencyPair());
        
        String pair = candle.getCurrencyPair();
        Map<Duration, CandleWindow> windowsByTimeframe = windowsByPairAndTimeframe
            .computeIfAbsent(pair, k -> new ConcurrentHashMap<>());

        // First, update the base timeframe window
        updateWindow(windowsByTimeframe, candle, baseCandleTimeframe);

        // Then aggregate and update higher timeframe windows
        for (Duration timeframe : supportedTimeframes) {
            if (timeframe.compareTo(baseCandleTimeframe) > 0) {
                aggregateAndUpdateWindow(windowsByTimeframe, candle, timeframe);
            }
        }
        
        logger.atInfo().log("Candle processing complete for %s", pair);
    }

    @Override
    public List<Candle> getCandlesForTimeframe(
            Duration timeframe, int windowSize, String currencyPair) {
        logger.atInfo().log(
            "Retrieving candles for %s, timeframe=%s, windowSize=%d",
            currencyPair, timeframe, windowSize);
            
        Map<Duration, CandleWindow> windowsByTimeframe = 
            windowsByPairAndTimeframe.get(currencyPair);
            
        if (windowsByTimeframe == null) {
            logger.atWarning().log("No data found for currency pair: %s", currencyPair);
            return ImmutableList.of();
        }
        
        CandleWindow window = windowsByTimeframe.get(timeframe);
        if (window == null) {
            logger.atWarning().log(
                "No data found for timeframe %s for currency pair %s", 
                timeframe, currencyPair);
            return ImmutableList.of();
        }
        
        return window.getCandles(windowSize);
    }

    @Override
    public List<Duration> getSupportedTimeframes() {
        return supportedTimeframes;
    }

    private void updateWindow(
            Map<Duration, CandleWindow> windowsByTimeframe, 
            Candle candle, 
            Duration timeframe) {
        CandleWindow window = windowsByTimeframe.computeIfAbsent(
            timeframe, 
            k -> new CandleWindow(timeframe)
        );
        window.addCandle(candle);
    }

    private void aggregateAndUpdateWindow(
            Map<Duration, CandleWindow> windowsByTimeframe,
            Candle candle,
            Duration timeframe) {
        // Get the window for this timeframe
        CandleWindow window = windowsByTimeframe.computeIfAbsent(
            timeframe,
            k -> new CandleWindow(timeframe)
        );

        // Check if we need to aggregate a new candle
        if (isTimeToAggregate(candle.getTimestamp(), timeframe)) {
            Duration lowerTimeframe = getNextLowerTimeframe(timeframe);
            List<Candle> candlesToAggregate = getCandlesForTimeframe(
                lowerTimeframe,
                getRequiredCandlesForAggregation(timeframe, lowerTimeframe),
                candle.getCurrencyPair()
            );
            
            if (!candlesToAggregate.isEmpty()) {
                Candle aggregatedCandle = aggregateCandles(candlesToAggregate);
                window.addCandle(aggregatedCandle);
            }
        }
    }

    private boolean isTimeToAggregate(long timestamp, Duration timeframe) {
        return timestamp % timeframe.toMillis() == 0;
    }

    private Duration getNextLowerTimeframe(Duration timeframe) {
        Duration previous = baseCandleTimeframe;
        for (Duration current : supportedTimeframes) {
            if (current.equals(timeframe)) {
                return previous;
            }
            previous = current;
        }
        throw new IllegalStateException("No lower timeframe found for: " + timeframe);
    }

    private int getRequiredCandlesForAggregation(Duration higher, Duration lower) {
        return (int) (higher.toMillis() / lower.toMillis());
    }

    private Candle aggregateCandles(List<Candle> candles) {
        if (candles.isEmpty()) {
            throw new IllegalArgumentException("Cannot aggregate empty candle list");
        }

        Candle first = candles.get(0);
        Candle last = candles.get(candles.size() - 1);

        double high = Double.MIN_VALUE;
        double low = Double.MAX_VALUE;
        double volume = 0;

        for (Candle candle : candles) {
            high = Math.max(high, candle.getHigh());
            low = Math.min(low, candle.getLow());
            volume += candle.getVolume();
        }

        return Candle.newBuilder()
            .setTimestamp(first.getTimestamp())
            .setCurrencyPair(first.getCurrencyPair())
            .setOpen(first.getOpen())
            .setHigh(high)
            .setLow(low)
            .setClose(last.getClose())
            .setVolume(volume)
            .build();
    }

    /**
     * Maintains a sliding window of candles for a specific timeframe.
     */
    private static class CandleWindow {
        private final List<Candle> candles = Collections.synchronizedList(new ArrayList<>());
        private final Duration timeframe;

        CandleWindow(Duration timeframe) {
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

    @AutoValue
    abstract static class ConfigImpl implements Config {
        static Config create(
                String kafkaTopic,
                String kafkaBootstrapServers,
                List<Duration> supportedTimeframes,
                Duration baseCandleTimeframe) {
            return new AutoValue_DataConsumptionLayerImpl_ConfigImpl(
                kafkaTopic,
                kafkaBootstrapServers,
                ImmutableList.copyOf(supportedTimeframes),
                baseCandleTimeframe);
        }
    }
}

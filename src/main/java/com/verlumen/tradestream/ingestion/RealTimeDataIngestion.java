package com.example.marketdata;

import com.google.protobuf.InvalidProtocolBufferException;
import io.reactivex.disposables.Disposable;
import marketdata.Marketdata.Candle;
import marketdata.Marketdata.Trade;
import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.knowm.xchange.currency.CurrencyPair;
import org.knowm.xchange.stream.core.StreamingExchange;
import org.knowm.xchange.stream.kraken.KrakenStreamingExchange;
import org.knowm.xchange.stream.core.StreamingExchangeFactory;
import org.knowm.xchange.stream.service.StreamingMarketDataService;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Real-time data ingestion module using XChange Streaming API.
 */
public class RealTimeDataIngestion {

    private final StreamingExchange streamingExchange;
    private final StreamingMarketDataService streamingMarketDataService;
    private final Set<CandleKey> processedTrades = ConcurrentHashMap.newKeySet();
    private final Map<String, CandleBuilder> candleBuilders = new ConcurrentHashMap<>();
    private final List<String> currencyPairs;
    private final long candleIntervalMillis = 60_000L; // 1-minute candles

    // Kafka producer
    private final KafkaProducer<String, byte[]> kafkaProducer;
    private final String kafkaTopic;

    private final List<Disposable> subscriptions = new ArrayList<>();

    public RealTimeDataIngestion(String exchangeClassName, List<String> currencyPairs, Properties kafkaProps, String kafkaTopic) throws ClassNotFoundException, IllegalAccessException, InstantiationException {
        this.streamingExchange = StreamingExchangeFactory.INSTANCE.createExchange(exchangeClassName);
        this.streamingMarketDataService = streamingExchange.getStreamingMarketDataService();
        this.currencyPairs = currencyPairs;
        this.kafkaProducer = new KafkaProducer<>(kafkaProps);
        this.kafkaTopic = kafkaTopic;
    }

    /**
     * Starts the data ingestion process.
     */
    public void start() {
        // Connect to the exchange
        streamingExchange.connect().blockingAwait();

        // Subscribe to trade streams
        for (String pair : currencyPairs) {
            CurrencyPair currencyPair = new CurrencyPair(pair);
            Disposable subscription = streamingMarketDataService.getTrades(currencyPair)
                    .subscribe(trade -> {
                        Trade protoTrade = Trade.newBuilder()
                                .setTimestamp(trade.getTimestamp().getTime())
                                .setExchange(streamingExchange.getExchangeSpecification().getExchangeName())
                                .setCurrencyPair(pair)
                                .setPrice(trade.getPrice().doubleValue())
                                .setVolume(trade.getOriginalAmount().doubleValue())
                                .setTradeId(trade.getId() != null ? trade.getId() : UUID.randomUUID().toString())
                                .build();

                        onTrade(protoTrade);
                    }, throwable -> {
                        // Handle errors
                        throwable.printStackTrace();
                    });

            subscriptions.add(subscription);
        }

        // Schedule handling of thinly traded markets
        Timer thinMarketTimer = new Timer();
        thinMarketTimer.scheduleAtFixedRate(new TimerTask() {
            @Override
            public void run() {
                handleThinlyTradedMarkets();
            }
        }, 0, 60_000); // Check every minute
    }

    /**
     * Processes an incoming trade.
     */
    public void onTrade(Trade trade) {
        long minuteTimestamp = getMinuteTimestamp(trade.getTimestamp());
        CandleKey key = new CandleKey(trade.getTradeId(), minuteTimestamp);

        if (processedTrades.contains(key)) {
            // Trade already processed; skip to ensure idempotency
            return;
        }

        processedTrades.add(key);

        // Aggregate trade into candle
        CandleBuilder builder = candleBuilders.computeIfAbsent(
                getCandleKey(trade.getCurrencyPair(), minuteTimestamp),
                k -> new CandleBuilder(trade.getCurrencyPair(), minuteTimestamp)
        );

        builder.addTrade(trade);
    }

    /**
     * Generates candles for thinly traded markets.
     */
    private void handleThinlyTradedMarkets() {
        long currentMinute = getMinuteTimestamp(System.currentTimeMillis());
        for (String pair : currencyPairs) {
            String key = getCandleKey(pair, currentMinute);
            candleBuilders.computeIfAbsent(key, k -> new CandleBuilder(pair, currentMinute))
                    .generateEmptyCandleIfNeeded();
        }
    }

    /**
     * Returns the minute timestamp for a given time.
     */
    private long getMinuteTimestamp(long timestamp) {
        return (timestamp / candleIntervalMillis) * candleIntervalMillis;
    }

    /**
     * Overloaded method for Date input.
     */
    private long getMinuteTimestamp(Date date) {
        return getMinuteTimestamp(date.getTime());
    }

    /**
     * Generates a unique key for candle builders.
     */
    private String getCandleKey(String currencyPair, long minuteTimestamp) {
        return currencyPair + ":" + minuteTimestamp;
    }

    /**
     * Inner class for building candles.
     */
    private class CandleBuilder {
        private final String currencyPair;
        private final long timestamp;
        private double open = Double.NaN;
        private double high = Double.NaN;
        private double low = Double.NaN;
        private double close = Double.NaN;
        private double volume = 0.0;
        private boolean hasTrades = false;

        public CandleBuilder(String currencyPair, long timestamp) {
            this.currencyPair = currencyPair;
            this.timestamp = timestamp;
        }

        public void addTrade(Trade trade) {
            double price = trade.getPrice();
            double tradeVolume = trade.getVolume();

            if (Double.isNaN(open)) {
                open = price;
                high = price;
                low = price;
            } else {
                high = Math.max(high, price);
                low = Math.min(low, price);
            }

            close = price;
            volume += tradeVolume;
            hasTrades = true;

            // Publish the candle if the interval has ended
            if (System.currentTimeMillis() >= timestamp + candleIntervalMillis) {
                publishCandle();
                candleBuilders.remove(getCandleKey(currencyPair, timestamp));
            }
        }

        public void generateEmptyCandleIfNeeded() {
            if (!hasTrades && System.currentTimeMillis() >= timestamp + candleIntervalMillis) {
                // Generate candle with last known price and zero volume
                double lastPrice = getLastKnownPrice(currencyPair);
                if (!Double.isNaN(lastPrice)) {
                    open = high = low = close = lastPrice;
                    volume = 0.0;
                    publishCandle();
                }
                candleBuilders.remove(getCandleKey(currencyPair, timestamp));
            }
        }

        private void publishCandle() {
            Candle candle = Candle.newBuilder()
                    .setTimestamp(timestamp)
                    .setCurrencyPair(currencyPair)
                    .setOpen(open)
                    .setHigh(high)
                    .setLow(low)
                    .setClose(close)
                    .setVolume(volume)
                    .build();

            // Publish the candle to Kafka
            onCandle(candle);
        }
    }

    /**
     * Callback for when a candle is ready.
     */
    public void onCandle(Candle candle) {
        try {
            // Serialize the Candle message to byte array
            byte[] candleBytes = candle.toByteArray();

            // Create a ProducerRecord with the candle bytes
            ProducerRecord<String, byte[]> record = new ProducerRecord<>(kafkaTopic, candle.getCurrencyPair(), candleBytes);

            // Send the record to Kafka
            kafkaProducer.send(record, (metadata, exception) -> {
                if (exception != null) {
                    // Handle exception
                    exception.printStackTrace();
                } else {
                    System.out.println("Published Candle to Kafka: " + candle);
                }
            });
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    /**
     * Retrieves the last known price for a currency pair.
     */
    private double getLastKnownPrice(String currencyPair) {
        // Implement logic to retrieve the last known price
        // For simplicity, returning NaN
        return Double.NaN;
    }

    /**
     * Closes the Kafka producer and disconnects from the exchange when shutting down.
     */
    public void shutdown() {
        // Unsubscribe from streams
        for (Disposable subscription : subscriptions) {
            subscription.dispose();
        }

        // Disconnect from the exchange
        streamingExchange.disconnect().blockingAwait();

        // Close the Kafka producer
        kafkaProducer.close(Duration.ofSeconds(5));
    }
}

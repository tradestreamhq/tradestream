package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.execution.RunMode;
import com.verlumen.tradestream.kafka.KafkaProperties;

record IngestionConfig(
    String candlePublisherTopic,
    String coinMarketCapApiKey,
    int topCryptocurrencyCount,
    String exchangeName,
    long candleIntervalMillis,
    RunMode runMode,
    KafkaProperties kafkaProperties) {}

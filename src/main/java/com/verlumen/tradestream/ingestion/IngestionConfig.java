package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.execution.RunMode;

record IngestionConfig(
    String coinMarketCapApiKey,
    int topCryptocurrencyCount,
    String exchangeName,
    long candleIntervalMillis,
    RunMode runMode,
    String kafkaBootstrapServers,
    String tradeTopic) {}

package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.execution.RunMode;

record IngestionConfig(
    String candlePublisherTopic,
    String coinMarketCapApiKey,
    int topCryptocurrencyCount,
    String exchangeName,
    long candleIntervalMillis,
    RunMode runMode) {}

package com.verlumen.tradestream.ingestion;

import com.verlumen.tradestream.execution.RunMode;

record IngestionConfig(
    String exchangeName,
    RunMode runMode,
    String kafkaBootstrapServers,
    String tradeTopic) {}

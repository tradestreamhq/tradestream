package com.verlumen.tradestream.pipeline;

import com.verlumen.tradestream.execution.RunMode;

record PipelineConfig(
    String exchangeName,
    String bootstrapServers,
    String tradeTopic,
    String signalTopic,
    RunMode runMode) {
  static PipelineConfig create(
      String exchangeName,
      String bootstrapServers,
      String tradeTopic,
      String signalTopic,
      String runMode) {
    return new PipelineConfig(
        exchangeName,
        bootstrapServers,
        tradeTopic,
        signalTopic,
        RunMode.fromString(runMode));
  }
}

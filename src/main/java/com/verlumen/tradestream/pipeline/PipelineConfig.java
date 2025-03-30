package com.verlumen.tradestream.pipeline;

import com.verlumen.tradestream.execution.RunMode;

record PipelineConfig(
    String exchangeName,
    String bootstrapServers,
    String signalTopic,
    RunMode runMode) {
  static PipelineConfig create(
      String exchangeName,
      String bootstrapServers,
      String signalTopic,
      String runMode) {
    return new PipelineConfig(
        exchangeName,
        bootstrapServers,
        signalTopic,
        RunMode.fromString(runMode));
  }
}

package com.verlumen.tradestream.pipeline;

import com.verlumen.tradestream.execution.RunMode;

record PipelineConfig(
    String bootstrapServers,
    String tradeTopic,
    String signalTopic,
    RunMode runMode) {
  static PipelineConfig create(
      String bootstrapServers,
      String tradeTopic,
      String signalTopic,
      String runMode) {
    return new PipelineConfig(
        bootstrapServers,
        tradeTopic,
        signalTopic,
        RunMode.fromString(runMode));
  }
}

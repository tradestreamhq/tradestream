package com.verlumen.tradestream.pipeline;

record PipelineConfig(String bootstrapServers, String tradeTopic, String runMode) {
  static PipelineConfig create(String bootstrapServers, String tradeTopic, String runMode) {
    return new PipelineConfig(bootstrapServers, tradeTopic, runMode);
  }
}

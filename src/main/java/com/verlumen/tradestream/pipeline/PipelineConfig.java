package com.verlumen.tradestream.pipeline;

import org.joda.time.Duration;

record PipelineConfig(String bootstrapServers, String tradeTopic, String runMode, Duration allowedLateness, Duration windowDuration) {
  private static final Duration FIVE_SECONDS = Duration.ofSeconds(5);
  private static final Duration ONE_MINUTE = Duration.ofMinutes(1);

  static PipelineConfig create(String bootstrapServers, String tradeTopic, String runMode, Duration allowedLateness) {
    return new PipelineConfig(bootstrapServers, tradeTopic, runMode, FIVE_SECONDS, ONE_MINUTE);
  }
}

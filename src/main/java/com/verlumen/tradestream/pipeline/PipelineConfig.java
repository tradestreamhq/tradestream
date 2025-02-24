package com.verlumen.tradestream.pipeline;

import org.joda.time.Duration;

record PipelineConfig(
    String bootstrapServers,
    String tradeTopic,
    String runMode,
    Duration allowedLateness,
    Duration windowDuration,
    Duration allowedTimestampSkew) {
  private static final Duration FIFTEEN_MINUTES = Duration.standardMinutes(15);
  private static final Duration FIVE_SECONDS = Duration.standardSeconds(5);
  private static final Duration ONE_MINUTE = Duration.standardMinutes(1);

  static PipelineConfig create(String bootstrapServers, String tradeTopic, String runMode) {
    return new PipelineConfig(
        bootstrapServers, tradeTopic, runMode, FIVE_SECONDS, ONE_MINUTE, FIFTEEN_MINUTES);
  }
}

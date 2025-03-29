package com.verlumen.tradestream.pipeline;

import com.verlumen.tradestream.execution.RunMode;
import org.joda.time.Duration;

record PipelineConfig(
    String bootstrapServers,
    String tradeTopic,
    String signalTopic,
    RunMode runMode,
    Duration allowedLateness,
    Duration windowDuration,
    Duration allowedTimestampSkew) {
  private static final Duration FIVE_SECONDS = Duration.standardSeconds(5);
  private static final Duration ONE_MINUTE = Duration.standardMinutes(1);
  private static final Duration THIRTY_MINUTES = Duration.standardMinutes(30);

  static PipelineConfig create(
      String bootstrapServers,
      String tradeTopic,
      String signalTopic,
      String runMode) {
    return new PipelineConfig(
        bootstrapServers,
        tradeTopic,
        signalTopic,
        RunMode.fromString(runMode),
        FIVE_SECONDS,
        ONE_MINUTE,
        THIRTY_MINUTES);
  }
}

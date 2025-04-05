package com.verlumen.tradestream.pipeline;

import org.joda.time.Duration;

record TimingConfig(
    Duration allowedLateness,
    Duration windowDuration,
    Duration allowedTimestampSkew) {
  private static final Duration TWO_SECONDS = Duration.standardSeconds(2);
  private static final Duration ONE_MINUTE = Duration.standardMinutes(1);
  private static final Duration TWO_MINUTES = Duration.standardMinutes(2);

  static TimingConfig create() {
    return new TimingConfig(
        TWO_SECONDS,
        ONE_MINUTE,
        TWO_MINUTES);
  }
}

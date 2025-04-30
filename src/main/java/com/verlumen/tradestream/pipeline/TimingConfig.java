package com.verlumen.tradestream.pipeline;

import org.joda.time.Duration;

record TimingConfig(
    Duration allowedLateness,
    Duration windowDuration) {
  private static final Duration TWO_SECONDS = Duration.standardSeconds(2);
  private static final Duration ONE_MINUTE = Duration.standardMinutes(1);

  static TimingConfig create() {
    return new TimingConfig(
        TWO_SECONDS,
        ONE_MINUTE);
  }
}

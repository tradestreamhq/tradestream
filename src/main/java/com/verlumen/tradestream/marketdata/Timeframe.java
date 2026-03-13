package com.verlumen.tradestream.marketdata;

import java.time.Duration;

/** Supported candle timeframes for aggregation. */
public enum Timeframe {
  ONE_MINUTE(Duration.ofMinutes(1), "1m"),
  FIVE_MINUTES(Duration.ofMinutes(5), "5m"),
  FIFTEEN_MINUTES(Duration.ofMinutes(15), "15m"),
  ONE_HOUR(Duration.ofHours(1), "1h"),
  FOUR_HOURS(Duration.ofHours(4), "4h"),
  ONE_DAY(Duration.ofDays(1), "1d");

  private final Duration duration;
  private final String label;

  Timeframe(Duration duration, String label) {
    this.duration = duration;
    this.label = label;
  }

  public Duration getDuration() {
    return duration;
  }

  public String getLabel() {
    return label;
  }

  /** Returns the start of the period that contains the given epoch millis. */
  public long alignToInterval(long epochMillis) {
    long durationMillis = duration.toMillis();
    return (epochMillis / durationMillis) * durationMillis;
  }

  /** Parse a timeframe label string like "1m", "5m", "1h" etc. */
  public static Timeframe fromLabel(String label) {
    for (Timeframe tf : values()) {
      if (tf.label.equals(label)) {
        return tf;
      }
    }
    throw new IllegalArgumentException("Unknown timeframe: " + label);
  }
}

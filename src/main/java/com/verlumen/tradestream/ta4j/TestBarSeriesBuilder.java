package com.verlumen.tradestream.ta4j;

import static org.ta4j.core.num.DecimalNum.valueOf;

import java.time.Duration;
import java.time.ZonedDateTime;
import org.ta4j.core.Bar;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;

/** Utility class for creating test bar series and bars for ta4j 0.18 compatibility. */
public final class TestBarSeriesBuilder {

  private TestBarSeriesBuilder() {
    // Utility class
  }

  /** Creates an empty bar series for testing. */
  public static BarSeries createBarSeries() {
    return new BaseBarSeriesBuilder().withName("testSeries").build();
  }

  /**
   * Creates a bar with the given time and price values. All OHLC values are set to the same price
   * for simplicity in tests.
   */
  public static Bar createBar(ZonedDateTime time, double price) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time.toInstant(),
        valueOf(price), // open
        valueOf(price), // high
        valueOf(price), // low
        valueOf(price), // close
        valueOf(100.0), // volume
        valueOf(0.0), // amount
        0L // trades
        );
  }

  /** Creates a bar with the given time and OHLC values. */
  public static Bar createBar(
      ZonedDateTime time, double open, double high, double low, double close, double volume) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time.toInstant(),
        valueOf(open),
        valueOf(high),
        valueOf(low),
        valueOf(close),
        valueOf(volume),
        valueOf(0.0), // amount
        0L // trades
        );
  }
}

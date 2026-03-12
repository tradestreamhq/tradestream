package com.verlumen.tradestream.strategies.doubleemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.averages.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public class DoubleEmaCrossoverStrategyFactoryTest {
  private static final int SHORT_EMA = 3;
  private static final int LONG_EMA = 7;

  private DoubleEmaCrossoverStrategyFactory factory;

  private DoubleEmaCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging EMA calculations
  private EMAIndicator shortEma;
  private EMAIndicator longEma;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new DoubleEmaCrossoverStrategyFactory();

    // Standard parameters
    params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();

    // Initialize series
    series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    // ---------------------------------------------------------------------
    // 1) Extended downward baseline to allow EMA warmup (need > longEma bars)
    //    so shortEma < longEma is established before the cross-up
    // ---------------------------------------------------------------------
    double price = 50.0;
    for (int i = 0; i < 14; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price -= 0.5;
    }

    // ---------------------------------------------------------------------
    // 2) Strong upward movement forces a strict cross-up
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(14), 65.0));
    series.addBar(createBar(now.plusMinutes(15), 80.0));
    series.addBar(createBar(now.plusMinutes(16), 85.0));
    series.addBar(createBar(now.plusMinutes(17), 90.0));

    // ---------------------------------------------------------------------
    // 3) Then a strong downward movement forces a strict cross-down
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(18), 40.0));
    series.addBar(createBar(now.plusMinutes(19), 30.0));
    series.addBar(createBar(now.plusMinutes(20), 25.0));

    // Initialize indicators for debugging
    closePrice = new ClosePriceIndicator(series);
    shortEma = new EMAIndicator(closePrice, SHORT_EMA);
    longEma = new EMAIndicator(closePrice, LONG_EMA);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenShortEmaCrossesAboveLongEma() {
    // No entry signal during baseline
    assertThat(strategy.getEntryRule().isSatisfied(13)).isFalse();

    // Cross-up should trigger after strong upward price movement
    boolean entryFound = false;
    for (int i = 14; i <= 17; i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entryFound = true;
        break;
      }
    }
    assertThat(entryFound).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenShortEmaCrossesBelowLongEma() {
    // No exit signal before the drop
    assertThat(strategy.getExitRule().isSatisfied(17)).isFalse();

    // Cross-down should trigger after strong downward price movement
    boolean exitFound = false;
    for (int i = 18; i <= 20; i++) {
      if (strategy.getExitRule().isSatisfied(i)) {
        exitFound = true;
        break;
      }
    }
    assertThat(exitFound).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateShortEmaPeriod() throws InvalidProtocolBufferException {
    params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(-1)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateLongEmaPeriod() throws InvalidProtocolBufferException {
    params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(-1)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateEmaPeriodOrdering() throws InvalidProtocolBufferException {
    params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(LONG_EMA)
            .setLongEmaPeriod(SHORT_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  /** Helper for creating a Bar with a specific close price. */
  private BaseBar createBar(ZonedDateTime time, double price) {
    Duration duration = Duration.ofMinutes(1);
    Instant endTime = time.toInstant();
    Instant beginTime = endTime.minus(duration);
    return new BaseBar(
        duration,
        beginTime,
        endTime,
        DecimalNum.valueOf(price), // open
        DecimalNum.valueOf(price), // high
        DecimalNum.valueOf(price), // low
        DecimalNum.valueOf(price), // close
        DecimalNum.valueOf(100.0), // volume
        DecimalNum.valueOf(0), // amount
        0 // trades
        );
  }
}

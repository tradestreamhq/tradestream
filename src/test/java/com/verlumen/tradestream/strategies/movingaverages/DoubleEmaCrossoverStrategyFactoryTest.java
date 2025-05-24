package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.DoubleEmaCrossoverParameters;
import com.verlumen.tradestream.strategies.StrategyType;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

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
    factory = DoubleEmaCrossoverStrategyFactory.create();

    // Standard parameters
    params =
        DoubleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // ---------------------------------------------------------------------
    // 1) Downward baseline so shortEma < longEma by bar 6
    //    This ensures a strict cross-up is possible at bar 7.
    // ---------------------------------------------------------------------
    // Bar 0 to 6: descending prices: 50 -> 49 -> 48 -> 47 -> 46 -> 45 -> 44
    double price = 50.0;
    for (int i = 0; i < 7; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price -= 1.0;
    }

    // ---------------------------------------------------------------------
    // 2) Strong upward movement forces a strict cross-up between bar 6 & 7
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(7), 65.0));
    series.addBar(createBar(now.plusMinutes(8), 80.0));
    series.addBar(createBar(now.plusMinutes(9), 85.0));
    series.addBar(createBar(now.plusMinutes(10), 90.0));

    // ---------------------------------------------------------------------
    // 3) Then a strong downward movement forces a strict cross-down
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(11), 40.0));
    series.addBar(createBar(now.plusMinutes(12), 30.0));
    series.addBar(createBar(now.plusMinutes(13), 25.0));

    // Initialize indicators for debugging
    closePrice = new ClosePriceIndicator(series);
    shortEma = new EMAIndicator(closePrice, SHORT_EMA);
    longEma = new EMAIndicator(closePrice, LONG_EMA);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsDoubleEmaCrossover() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.DOUBLE_EMA_CROSSOVER);
  }

  @Test
  public void entryRule_shouldTrigger_whenShortEmaCrossesAboveLongEma() {
    // Log EMA values around the expected cross-up
    for (int i = 6; i <= 9; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, Short EMA: %.2f, Long EMA: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          shortEma.getValue(i).doubleValue(),
          longEma.getValue(i).doubleValue());
    }

    // No entry signal during baseline
    assertThat(strategy.getEntryRule().isSatisfied(6)).isFalse();

    // Strict cross-up typically recognized at bar 7
    assertThat(strategy.getEntryRule().isSatisfied(7)).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenShortEmaCrossesBelowLongEma() {
    // Log EMA values around the expected cross-down
    for (int i = 10; i <= 13; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, Short EMA: %.2f, Long EMA: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          shortEma.getValue(i).doubleValue(),
          longEma.getValue(i).doubleValue());
    }

    // No exit signal before the drop
    assertThat(strategy.getExitRule().isSatisfied(10)).isFalse();

    // Strict cross-down typically recognized at bar 11
    assertThat(strategy.getExitRule().isSatisfied(11)).isTrue();
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
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        price, // open
        price, // high
        price, // low
        price, // close
        100.0 // volume
        );
  }
}

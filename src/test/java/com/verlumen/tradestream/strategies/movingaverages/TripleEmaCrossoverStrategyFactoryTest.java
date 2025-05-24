package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StrategyType;
import com.verlumen.tradestream.strategies.TripleEmaCrossoverParameters;
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
public class TripleEmaCrossoverStrategyFactoryTest {
  private static final int SHORT_EMA = 5;
  private static final int MEDIUM_EMA = 10;
  private static final int LONG_EMA = 20;
  private TripleEmaCrossoverStrategyFactory factory;
  private TripleEmaCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging EMA calculations
  private EMAIndicator shortEma;
  private EMAIndicator mediumEma;
  private EMAIndicator longEma;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = TripleEmaCrossoverStrategyFactory.create();
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setMediumEmaPeriod(MEDIUM_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // ---------------------------------------------------------------------
    // 1) Baseline - shortEma < mediumEma < longEma
    // ---------------------------------------------------------------------
    double price = 50.0;
    for (int i = 0; i < 7; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price -= 1.0;
    }

    // ---------------------------------------------------------------------
    // 2) Upward movement - shortEma > mediumEma and mediumEma > longEma by bar 7
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(7), 65.0));
    series.addBar(createBar(now.plusMinutes(8), 80.0));
    series.addBar(createBar(now.plusMinutes(9), 85.0));
    series.addBar(createBar(now.plusMinutes(10), 90.0));

    // ---------------------------------------------------------------------
    // 3) Downward movement - shortEma < mediumEma and mediumEma < longEma by bar 11
    // ---------------------------------------------------------------------
    series.addBar(createBar(now.plusMinutes(11), 40.0));
    series.addBar(createBar(now.plusMinutes(12), 30.0));
    series.addBar(createBar(now.plusMinutes(13), 25.0));

    // Initialize indicators for debugging
    closePrice = new ClosePriceIndicator(series);
    shortEma = new EMAIndicator(closePrice, SHORT_EMA);
    mediumEma = new EMAIndicator(closePrice, MEDIUM_EMA);
    longEma = new EMAIndicator(closePrice, LONG_EMA);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsTripleEmaCrossover() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.TRIPLE_EMA_CROSSOVER);
  }

  @Test
  public void
      entryRule_shouldTrigger_whenShortEmaCrossesAboveMediumEmaOrMediumEmaCrossesAboveLongEma() {
    for (int i = 6; i <= 10; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, Short EMA: %.2f, Medium EMA: %.2f, Long EMA: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          shortEma.getValue(i).doubleValue(),
          mediumEma.getValue(i).doubleValue(),
          longEma.getValue(i).doubleValue());
    }
    // No entry signal before crossover
    assertThat(strategy.getEntryRule().isSatisfied(6)).isFalse();

    // Entry signal at bar 7
    assertThat(strategy.getEntryRule().isSatisfied(7)).isTrue();
  }

  @Test
  public void
      exitRule_shouldTrigger_whenShortEmaCrossesBelowMediumEmaOrMediumEmaCrossesBelowLongEma() {
    for (int i = 10; i <= 13; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, Short EMA: %.2f, Medium EMA: %.2f, Long EMA: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          shortEma.getValue(i).doubleValue(),
          mediumEma.getValue(i).doubleValue(),
          longEma.getValue(i).doubleValue());
    }
    // No exit signal before crossover
    assertThat(strategy.getExitRule().isSatisfied(10)).isFalse();

    // Exit signal at bar 11
    assertThat(strategy.getExitRule().isSatisfied(12)).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateShortEmaPeriod() throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(-1)
            .setMediumEmaPeriod(MEDIUM_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateMediumEmaPeriod() throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setMediumEmaPeriod(-1)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateLongEmaPeriod() throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setMediumEmaPeriod(MEDIUM_EMA)
            .setLongEmaPeriod(-1)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateEmaPeriodOrdering1() throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(MEDIUM_EMA)
            .setMediumEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateEmaPeriodOrdering2() throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setMediumEmaPeriod(LONG_EMA)
            .setLongEmaPeriod(MEDIUM_EMA)
            .build();
    factory.createStrategy(series, params);
  }

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

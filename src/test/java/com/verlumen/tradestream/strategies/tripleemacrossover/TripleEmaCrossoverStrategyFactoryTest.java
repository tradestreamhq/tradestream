package com.verlumen.tradestream.strategies.tripleemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
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
  private static final int SHORT_EMA = 3;
  private static final int MEDIUM_EMA = 5;
  private static final int LONG_EMA = 7;

  private TripleEmaCrossoverStrategyFactory factory;

  private TripleEmaCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  private EMAIndicator shortEma;
  private EMAIndicator mediumEma;
  private EMAIndicator longEma;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new TripleEmaCrossoverStrategyFactory();

    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setMediumEmaPeriod(MEDIUM_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();

    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Downward baseline so shortEma < mediumEma < longEma by bar 6
    double price = 50.0;
    for (int i = 0; i < 7; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price -= 1.0;
    }

    // Strong upward movement forces a cross-up
    series.addBar(createBar(now.plusMinutes(7), 65.0));
    series.addBar(createBar(now.plusMinutes(8), 80.0));
    series.addBar(createBar(now.plusMinutes(9), 85.0));
    series.addBar(createBar(now.plusMinutes(10), 90.0));

    // Strong downward movement forces a cross-down
    series.addBar(createBar(now.plusMinutes(11), 40.0));
    series.addBar(createBar(now.plusMinutes(12), 30.0));
    series.addBar(createBar(now.plusMinutes(13), 25.0));

    closePrice = new ClosePriceIndicator(series);
    shortEma = new EMAIndicator(closePrice, SHORT_EMA);
    mediumEma = new EMAIndicator(closePrice, MEDIUM_EMA);
    longEma = new EMAIndicator(closePrice, LONG_EMA);

    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenShortEmaCrossesAboveMediumOrLongEma() {
    // No entry signal during baseline
    assertThat(strategy.getEntryRule().isSatisfied(6)).isFalse();

    // Cross-up recognized after strong upward movement
    assertThat(strategy.getEntryRule().isSatisfied(7)).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenShortEmaCrossesBelowMediumOrLongEma() {
    // No exit signal before the drop
    assertThat(strategy.getExitRule().isSatisfied(10)).isFalse();

    // Cross-down recognized after strong downward movement
    assertThat(strategy.getExitRule().isSatisfied(11)).isTrue();
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
  public void validateEmaPeriodOrdering_mediumGreaterThanShort()
      throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(MEDIUM_EMA)
            .setMediumEmaPeriod(SHORT_EMA)
            .setLongEmaPeriod(LONG_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateEmaPeriodOrdering_longGreaterThanMedium()
      throws InvalidProtocolBufferException {
    params =
        TripleEmaCrossoverParameters.newBuilder()
            .setShortEmaPeriod(SHORT_EMA)
            .setMediumEmaPeriod(LONG_EMA)
            .setLongEmaPeriod(MEDIUM_EMA)
            .build();
    factory.createStrategy(series, params);
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    return new BaseBar(Duration.ofMinutes(1), time, price, price, price, price, 100.0);
  }
}

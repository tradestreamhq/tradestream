package com.verlumen.tradestream.strategies.tripleemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.TripleEmaCrossoverParameters;
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

    series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    // Extended downward baseline to allow EMA warmup (need > longEma bars)
    double price = 50.0;
    for (int i = 0; i < 14; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price -= 0.5;
    }

    // Strong upward movement forces a cross-up
    series.addBar(createBar(now.plusMinutes(14), 65.0));
    series.addBar(createBar(now.plusMinutes(15), 80.0));
    series.addBar(createBar(now.plusMinutes(16), 85.0));
    series.addBar(createBar(now.plusMinutes(17), 90.0));

    // Strong downward movement forces a cross-down
    series.addBar(createBar(now.plusMinutes(18), 40.0));
    series.addBar(createBar(now.plusMinutes(19), 30.0));
    series.addBar(createBar(now.plusMinutes(20), 25.0));

    closePrice = new ClosePriceIndicator(series);
    shortEma = new EMAIndicator(closePrice, SHORT_EMA);
    mediumEma = new EMAIndicator(closePrice, MEDIUM_EMA);
    longEma = new EMAIndicator(closePrice, LONG_EMA);

    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenShortEmaCrossesAboveMediumOrLongEma() {
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
  public void exitRule_shouldTrigger_whenShortEmaCrossesBelowMediumOrLongEma() {
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
    Instant endTime = time.toInstant();
    Instant beginTime = endTime.minus(Duration.ofMinutes(1));
    return new BaseBar(
        Duration.ofMinutes(1),
        beginTime,
        endTime,
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(price),
        DecimalNum.valueOf(100.0),
        DecimalNum.valueOf(0),
        0);
  }
}

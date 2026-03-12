package com.verlumen.tradestream.strategies.rsiemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RsiEmaCrossoverParameters;
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
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public class RsiEmaCrossoverStrategyFactoryTest {
  private static final int RSI_PERIOD = 14;
  private static final int EMA_PERIOD = 10;

  private RsiEmaCrossoverStrategyFactory factory;
  private RsiEmaCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  @Before
  public void setUp() {
    factory = new RsiEmaCrossoverStrategyFactory();

    // Standard parameters
    params =
        RsiEmaCrossoverParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setEmaPeriod(EMA_PERIOD)
            .build();

    // Initialize series
    series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    // Build price data that creates clear RSI/EMA crossovers
    // Phase 1 (bars 0-29): Steady gentle decline to establish low RSI and low RSI EMA
    int barIdx = 0;
    double price = 100.0;
    for (int i = 0; i < 30; i++) {
      price -= 0.3;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 2 (bars 30-44): Gentle price increase - enough for RSI to cross above
    // its EMA but NOT enough to push RSI above 70
    for (int i = 0; i < 15; i++) {
      price += 0.5;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 3 (bars 45-54): Flat stabilization
    for (int i = 0; i < 10; i++) {
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 4 (bars 55-69): Gentle price decline - enough for RSI to cross below
    // its EMA but NOT enough to push RSI below 30
    for (int i = 0; i < 15; i++) {
      price -= 0.5;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 5 (bars 70-79): Flat stabilization
    for (int i = 0; i < 10; i++) {
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenRsiCrossesAboveEmaAndNotOverbought() {
    // Find when entry rule is satisfied during/after the price increase phase
    boolean entryTriggered = false;
    for (int i = 30; i <= 54; i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entryTriggered = true;
        break;
      }
    }

    assertThat(entryTriggered).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenRsiCrossesBelowEmaAndNotOversold() {
    // Find when exit rule is satisfied during/after the price decline phase
    boolean exitTriggered = false;
    for (int i = 55; i <= 79; i++) {
      if (strategy.getExitRule().isSatisfied(i)) {
        exitTriggered = true;
        break;
      }
    }

    assertThat(exitTriggered).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateRsiPeriod() {
    params =
        RsiEmaCrossoverParameters.newBuilder().setRsiPeriod(-1).setEmaPeriod(EMA_PERIOD).build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateEmaPeriod() {
    params =
        RsiEmaCrossoverParameters.newBuilder().setRsiPeriod(RSI_PERIOD).setEmaPeriod(-1).build();
    factory.createStrategy(series, params);
  }

  @Test
  public void getDefaultParameters_returnsExpectedValues() {
    RsiEmaCrossoverParameters defaultParams = factory.getDefaultParameters();
    assertThat(defaultParams.getRsiPeriod()).isEqualTo(14);
    assertThat(defaultParams.getEmaPeriod()).isEqualTo(10);
  }

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

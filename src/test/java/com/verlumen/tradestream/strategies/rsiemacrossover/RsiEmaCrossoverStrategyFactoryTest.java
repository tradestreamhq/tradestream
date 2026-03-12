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

    // Initialize series with price data designed to create RSI/EMA crossovers.
    // The key insight: we need oscillating prices first to give RSI meaningful
    // values (~50) and establish the EMA warmup, then directional moves to
    // create crossovers while keeping RSI in the 30-70 range.
    series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();

    int barIdx = 0;
    double price = 100.0;

    // Phase 1 (bars 0-24): Oscillating prices to establish RSI ~50 and warm up EMA
    for (int i = 0; i < 25; i++) {
      price += (i % 2 == 0) ? 1.0 : -1.0;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 2 (bars 25-34): Declining prices to push RSI below its EMA
    for (int i = 0; i < 10; i++) {
      price -= 0.8;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 3 (bars 35-44): Rising prices to make RSI cross above its EMA
    for (int i = 0; i < 10; i++) {
      price += 0.8;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 4 (bars 45-54): Flat stabilization
    for (int i = 0; i < 10; i++) {
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 5 (bars 55-64): Rising prices to push RSI above its EMA
    for (int i = 0; i < 10; i++) {
      price += 0.8;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 6 (bars 65-74): Declining prices to make RSI cross below its EMA
    for (int i = 0; i < 10; i++) {
      price -= 0.8;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Phase 7 (bars 75-84): Flat stabilization
    for (int i = 0; i < 10; i++) {
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenRsiCrossesAboveEmaAndNotOverbought() {
    // Find when entry rule is satisfied during/after the price increase phases
    boolean entryTriggered = false;
    for (int i = 25; i <= 54; i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entryTriggered = true;
        break;
      }
    }

    assertThat(entryTriggered).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenRsiCrossesBelowEmaAndNotOversold() {
    // Find when exit rule is satisfied during/after the price decline phases
    boolean exitTriggered = false;
    for (int i = 25; i <= 84; i++) {
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

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
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.averages.EMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public class RsiEmaCrossoverStrategyFactoryTest {
  private static final int RSI_PERIOD = 14;
  private static final int EMA_PERIOD = 10;

  private RsiEmaCrossoverStrategyFactory factory;
  private RsiEmaCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging RSI and EMA calculations
  private RSIIndicator rsi;
  private EMAIndicator rsiEma;
  private ClosePriceIndicator closePrice;

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

    // Bars 0-24: Steady decline to bring RSI well below its EMA
    int barIdx = 0;
    double price = 60.0;
    for (int i = 0; i < 25; i++) {
      price -= 0.5;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Bars 25-34: Sharp price increase to make RSI cross above its EMA
    for (int i = 0; i < 10; i++) {
      price += 2.0;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Bars 35-39: Stabilize
    for (int i = 0; i < 5; i++) {
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Bars 40-49: Sharp price decline to make RSI cross below its EMA
    for (int i = 0; i < 10; i++) {
      price -= 2.0;
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Bars 50-54: Stabilize
    for (int i = 0; i < 5; i++) {
      series.addBar(createBar(now.plusMinutes(barIdx++), price));
    }

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    rsi = new RSIIndicator(closePrice, RSI_PERIOD);
    rsiEma = new EMAIndicator(rsi, EMA_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenRsiCrossesAboveEmaAndNotOverbought() {
    // Log RSI values to diagnose
    for (int i = 20; i <= 39; i++) {
      System.out.printf(
          "Bar %d - RSI: %.2f, RSI EMA: %.2f, Entry: %s%n",
          i,
          rsi.getValue(i).doubleValue(),
          rsiEma.getValue(i).doubleValue(),
          strategy.getEntryRule().isSatisfied(i));
    }

    // Find when entry rule is satisfied during the price increase phase
    boolean entryTriggered = false;
    for (int i = 25; i <= 39; i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entryTriggered = true;
        break;
      }
    }

    assertThat(entryTriggered).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenRsiCrossesBelowEmaAndNotOversold() {
    // Find when exit rule is satisfied during the price decline phase
    boolean exitTriggered = false;
    for (int i = 40; i <= 54; i++) {
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

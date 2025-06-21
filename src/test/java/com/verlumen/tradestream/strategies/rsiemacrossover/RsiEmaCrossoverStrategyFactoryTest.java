package com.verlumen.tradestream.strategies.rsiemacrossover;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RsiEmaCrossoverParameters;
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
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

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
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Bars 0-20: Create baseline with mixed price movements to establish RSI and EMA
    double[] baselinePrices = {
      50.0, 49.0, 51.0, 48.0, 52.0, 47.0, 53.0, 46.0, 54.0, 45.0,
      55.0, 44.0, 56.0, 43.0, 57.0, 42.0, 58.0, 41.0, 59.0, 40.0, 60.0
    };
    
    for (int i = 0; i < baselinePrices.length; i++) {
      series.addBar(createBar(now.plusMinutes(i), baselinePrices[i]));
    }

    // Bars 21-25: Create conditions for entry (RSI crosses above EMA, RSI not overbought)
    // Gradual price increase to make RSI rise but stay below 70
    series.addBar(createBar(now.plusMinutes(21), 61.0));
    series.addBar(createBar(now.plusMinutes(22), 62.0));
    series.addBar(createBar(now.plusMinutes(23), 63.0));
    series.addBar(createBar(now.plusMinutes(24), 64.0));
    series.addBar(createBar(now.plusMinutes(25), 65.0));

    // Bars 26-30: Create conditions for exit (RSI crosses below EMA, RSI not oversold)
    // Moderate price decrease to make RSI fall but stay above 30
    series.addBar(createBar(now.plusMinutes(26), 64.0));
    series.addBar(createBar(now.plusMinutes(27), 62.0));
    series.addBar(createBar(now.plusMinutes(28), 60.0));
    series.addBar(createBar(now.plusMinutes(29), 58.0));
    series.addBar(createBar(now.plusMinutes(30), 56.0));

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    rsi = new RSIIndicator(closePrice, RSI_PERIOD);
    rsiEma = new EMAIndicator(rsi, EMA_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsRsiEmaCrossover() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.RSI_EMA_CROSSOVER);
  }

  @Test
  public void entryRule_shouldTrigger_whenRsiCrossesAboveEmaAndNotOverbought() {
    // Log RSI and EMA values around the expected entry
    for (int i = 20; i <= 25; i++) {
      double rsiValue = rsi.getValue(i).doubleValue();
      double emaValue = rsiEma.getValue(i).doubleValue();
      System.out.printf(
          "Bar %d - Price: %.2f, RSI: %.2f, RSI EMA: %.2f, Entry Rule: %s%n",
          i,
          closePrice.getValue(i).doubleValue(),
          rsiValue,
          emaValue,
          strategy.getEntryRule().isSatisfied(i));
    }

    // Find when entry rule is satisfied
    boolean entryTriggered = false;
    int entryIndex = -1;
    for (int i = 21; i <= 25; i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        entryTriggered = true;
        entryIndex = i;
        break;
      }
    }

    System.out.println("Entry rule triggered at bar: " + entryIndex);
    assertThat(entryTriggered).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenRsiCrossesBelowEmaAndNotOversold() {
    // Log RSI and EMA values around the expected exit
    for (int i = 25; i <= 30; i++) {
      double rsiValue = rsi.getValue(i).doubleValue();
      double emaValue = rsiEma.getValue(i).doubleValue();
      System.out.printf(
          "Bar %d - Price: %.2f, RSI: %.2f, RSI EMA: %.2f, Exit Rule: %s%n",
          i,
          closePrice.getValue(i).doubleValue(),
          rsiValue,
          emaValue,
          strategy.getExitRule().isSatisfied(i));
    }

    // Find when exit rule is satisfied
    boolean exitTriggered = false;
    int exitIndex = -1;
    for (int i = 26; i <= 30; i++) {
      if (strategy.getExitRule().isSatisfied(i)) {
        exitTriggered = true;
        exitIndex = i;
        break;
      }
    }

    System.out.println("Exit rule triggered at bar: " + exitIndex);
    assertThat(exitTriggered).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateRsiPeriod() {
    params =
        RsiEmaCrossoverParameters.newBuilder()
            .setRsiPeriod(-1)
            .setEmaPeriod(EMA_PERIOD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateEmaPeriod() {
    params =
        RsiEmaCrossoverParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setEmaPeriod(-1)
            .build();
    factory.createStrategy(series, params);
  }

  @Test
  public void getDefaultParameters_returnsExpectedValues() {
    RsiEmaCrossoverParameters defaultParams = factory.getDefaultParameters();
    assertThat(defaultParams.getRsiPeriod()).isEqualTo(14);
    assertThat(defaultParams.getEmaPeriod()).isEqualTo(10);
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

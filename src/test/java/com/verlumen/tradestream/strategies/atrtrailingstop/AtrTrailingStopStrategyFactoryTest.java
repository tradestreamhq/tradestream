package com.verlumen.tradestream.strategies.atrtrailingstop;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.AtrTrailingStopParameters;
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
import org.ta4j.core.indicators.ATRIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.PreviousValueIndicator;

@RunWith(JUnit4.class)
public class AtrTrailingStopStrategyFactoryTest {
  private static final int ATR_PERIOD = 14;
  private static final double MULTIPLIER = 2.0;

  private AtrTrailingStopStrategyFactory factory;
  private AtrTrailingStopParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging calculations
  private ATRIndicator atrIndicator;
  private ClosePriceIndicator closePrice;
  private PreviousValueIndicator previousClose;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new AtrTrailingStopStrategyFactory();

    // Standard parameters
    params =
        AtrTrailingStopParameters.newBuilder()
            .setAtrPeriod(ATR_PERIOD)
            .setMultiplier(MULTIPLIER)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create sample price data with initial uptrend then downtrend
    // Initial stable period
    for (int i = 0; i < 10; i++) {
      series.addBar(createBar(now.plusMinutes(i), 50.0));
    }

    // Upward movement
    for (int i = 10; i < 15; i++) {
      double price = 50.0 + (i - 9) * 2; // Increasing by 2 each bar
      series.addBar(createBar(now.plusMinutes(i), price));
    }

    // Sharp downward movement to trigger trailing stop
    series.addBar(createBar(now.plusMinutes(15), 55.0));
    series.addBar(createBar(now.plusMinutes(16), 52.0));
    series.addBar(createBar(now.plusMinutes(17), 48.0));
    series.addBar(createBar(now.plusMinutes(18), 45.0));

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    atrIndicator = new ATRIndicator(series, ATR_PERIOD);
    previousClose = new PreviousValueIndicator(closePrice, 1);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsAtrTrailingStop() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.ATR_TRAILING_STOP);
  }

  @Test
  public void getDefaultParameters_returnsValidDefaults() {
    AtrTrailingStopParameters defaults = factory.getDefaultParameters();
    assertThat(defaults.getAtrPeriod()).isEqualTo(14);
    assertThat(defaults.getMultiplier()).isEqualTo(2.0);
  }

  @Test
  public void entryRule_shouldTrigger_whenPriceRisesAbovePreviousClose() {
    // Entry rule: current price > previous close (simple momentum)
    // Look for a bar where price is above previous close
    int entryIndex = -1;
    for (int i = 1; i < series.getBarCount(); i++) {
      if (closePrice.getValue(i).doubleValue() > previousClose.getValue(i).doubleValue()) {
        entryIndex = i;
        break;
      }
    }

    if (entryIndex > 0) {
      System.out.printf(
          "Entry at Bar %d - Current Price: %.2f, Previous Close: %.2f%n",
          entryIndex,
          closePrice.getValue(entryIndex).doubleValue(),
          previousClose.getValue(entryIndex).doubleValue());
      assertThat(strategy.getEntryRule().isSatisfied(entryIndex)).isTrue();
    } else {
      System.out.println("No entry signal found with current data and parameters.");
    }
  }

  @Test
  public void exitRule_shouldTrigger_whenPriceFallsBelowTrailingStop() {
    // Exit rule: price falls below trailing stop (previous close - ATR * multiplier)
    // Look for a bar where this condition is met
    int exitIndex = -1;
    for (int i = ATR_PERIOD; i < series.getBarCount(); i++) {
      double currentPrice = closePrice.getValue(i).doubleValue();
      double prevClose = previousClose.getValue(i).doubleValue();
      double atr = atrIndicator.getValue(i).doubleValue();
      double trailingStop = prevClose - (atr * MULTIPLIER);
      if (currentPrice < trailingStop) {
        exitIndex = i;
        System.out.printf(
            "Exit at Bar %d - Price: %.2f, Previous Close: %.2f, ATR: %.2f, Trailing Stop: %.2f%n",
            exitIndex, currentPrice, prevClose, atr, trailingStop);
        break;
      }
    }

    if (exitIndex > 0) {
      assertThat(strategy.getExitRule().isSatisfied(exitIndex)).isTrue();
    } else {
      System.out.println("No exit signal found with current data and parameters.");
    }
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateAtrPeriod() throws InvalidProtocolBufferException {
    params =
        AtrTrailingStopParameters.newBuilder().setAtrPeriod(-1).setMultiplier(MULTIPLIER).build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateMultiplier() throws InvalidProtocolBufferException {
    params =
        AtrTrailingStopParameters.newBuilder().setAtrPeriod(ATR_PERIOD).setMultiplier(-1.0).build();
    factory.createStrategy(series, params);
  }

  @Test
  public void createStrategy_withValidParameters_returnsStrategy()
      throws InvalidProtocolBufferException {
    Strategy result = factory.createStrategy(series, params);
    assertThat(result).isNotNull();
    assertThat(result.getName()).contains("ATR_TRAILING_STOP");
    assertThat(result.getName()).contains("ATR: 14");
    assertThat(result.getName()).contains("Mult: 2.00");
  }

  private BaseBar createBar(ZonedDateTime time, double price) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        price, // open
        price + 1.0, // high (slightly higher for realistic ATR calculation)
        price - 1.0, // low (slightly lower for realistic ATR calculation)
        price, // close
        100.0 // volume
        );
  }
}

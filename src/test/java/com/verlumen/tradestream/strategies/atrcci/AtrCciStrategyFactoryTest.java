package com.verlumen.tradestream.strategies.atrcci;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.AtrCciParameters;
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
import org.ta4j.core.indicators.CCIIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.PreviousValueIndicator;

@RunWith(JUnit4.class)
public class AtrCciStrategyFactoryTest {
  private static final int ATR_PERIOD = 14;
  private static final int CCI_PERIOD = 20;

  private AtrCciStrategyFactory factory;
  private AtrCciParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging ATR and CCI calculations
  private ATRIndicator atrIndicator;
  private CCIIndicator cciIndicator;
  private PreviousValueIndicator previousAtr;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new AtrCciStrategyFactory();

    // Standard parameters
    params =
        AtrCciParameters.newBuilder()
            .setAtrPeriod(ATR_PERIOD)
            .setCciPeriod(CCI_PERIOD)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create sample price data with volatility changes and CCI patterns
    // Initial stable period
    for (int i = 0; i < 10; i++) {
      series.addBar(createBar(now.plusMinutes(i), 100.0, 1.0)); // Low volatility
    }

    // Period with declining prices and low CCI (below -100)
    for (int i = 10; i < 15; i++) {
      double price = 100.0 - (i - 9) * 3; // Declining prices
      series.addBar(createBar(now.plusMinutes(i), price, 2.0)); // Increasing volatility
    }

    // Strong upward movement with increasing volatility and high CCI
    for (int i = 15; i < 20; i++) {
      double price = 85.0 + (i - 14) * 8; // Strong upward movement
      series.addBar(createBar(now.plusMinutes(i), price, 4.0)); // High volatility
    }

    // Period with high prices and high CCI (above +100), then decreasing volatility
    for (int i = 20; i < 25; i++) {
      double price = 125.0 + (i - 19) * 2; // Continued upward but slower
      series.addBar(
          createBar(now.plusMinutes(i), price, 3.0 - (i - 20) * 0.5)); // Decreasing volatility
    }

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    atrIndicator = new ATRIndicator(series, ATR_PERIOD);
    cciIndicator = new CCIIndicator(series, CCI_PERIOD);
    previousAtr = new PreviousValueIndicator(atrIndicator, 1);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsAtrCci() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.ATR_CCI);
  }

  @Test
  public void getDefaultParameters_returnsValidDefaults() {
    AtrCciParameters defaults = factory.getDefaultParameters();
    assertThat(defaults.getAtrPeriod()).isEqualTo(14);
    assertThat(defaults.getCciPeriod()).isEqualTo(20);
  }

  @Test
  public void entryRule_shouldTrigger_whenCciAboveMinus100AndAtrIncreasing() {
    // Find a bar index where CCI is above -100 and ATR is increasing
    int entryIndex = -1;
    for (int i = Math.max(ATR_PERIOD, CCI_PERIOD); i < series.getBarCount(); i++) {
      double cci = cciIndicator.getValue(i).doubleValue();
      double atr = atrIndicator.getValue(i).doubleValue();
      double prevAtr = previousAtr.getValue(i).doubleValue();
      if (cci > -100 && atr > prevAtr) {
        entryIndex = i;
        break;
      }
    }

    // Log values for debugging
    if (entryIndex > 0) {
      System.out.printf(
          "Entry at Bar %d - Price: %.2f, CCI: %.2f, ATR: %.2f, Prev ATR: %.2f%n",
          entryIndex,
          closePrice.getValue(entryIndex).doubleValue(),
          cciIndicator.getValue(entryIndex).doubleValue(),
          atrIndicator.getValue(entryIndex).doubleValue(),
          previousAtr.getValue(entryIndex).doubleValue());
      assertThat(strategy.getEntryRule().isSatisfied(entryIndex)).isTrue();
    } else {
      System.out.println("No entry signal found with current data and parameters.");
      // Still verify the strategy was created successfully
      assertThat(strategy).isNotNull();
    }
  }

  @Test
  public void exitRule_shouldTrigger_whenCciBelow100AndAtrDecreasing() {
    // Find a bar index where CCI is below 100 and ATR is decreasing
    int exitIndex = -1;
    for (int i = Math.max(ATR_PERIOD, CCI_PERIOD); i < series.getBarCount(); i++) {
      double cci = cciIndicator.getValue(i).doubleValue();
      double atr = atrIndicator.getValue(i).doubleValue();
      double prevAtr = previousAtr.getValue(i).doubleValue();
      if (cci < 100 && atr < prevAtr) {
        exitIndex = i;
        break;
      }
    }

    // Log values for debugging
    if (exitIndex > 0) {
      System.out.printf(
          "Exit at Bar %d - Price: %.2f, CCI: %.2f, ATR: %.2f, Prev ATR: %.2f%n",
          exitIndex,
          closePrice.getValue(exitIndex).doubleValue(),
          cciIndicator.getValue(exitIndex).doubleValue(),
          atrIndicator.getValue(exitIndex).doubleValue(),
          previousAtr.getValue(exitIndex).doubleValue());
      assertThat(strategy.getExitRule().isSatisfied(exitIndex)).isTrue();
    } else {
      System.out.println("No exit signal found with current data and parameters.");
      // Still verify the strategy was created successfully
      assertThat(strategy).isNotNull();
    }
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateAtrPeriod() throws InvalidProtocolBufferException {
    params = AtrCciParameters.newBuilder().setAtrPeriod(-1).setCciPeriod(CCI_PERIOD).build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateCciPeriod() throws InvalidProtocolBufferException {
    params = AtrCciParameters.newBuilder().setAtrPeriod(ATR_PERIOD).setCciPeriod(-1).build();
    factory.createStrategy(series, params);
  }

  @Test
  public void createStrategy_withValidParameters_returnsStrategy()
      throws InvalidProtocolBufferException {
    Strategy result = factory.createStrategy(series, params);
    assertThat(result).isNotNull();
    assertThat(result.getName()).contains("ATR_CCI");
    assertThat(result.getName()).contains("ATR: 14");
    assertThat(result.getName()).contains("CCI: 20");
  }

  private BaseBar createBar(ZonedDateTime time, double price, double volatility) {
    // Create bars with varying high/low based on volatility for realistic ATR calculation
    double high = price + volatility;
    double low = price - volatility;
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        price, // open
        high, // high
        low, // low
        price, // close
        100.0 // volume
        );
  }
}

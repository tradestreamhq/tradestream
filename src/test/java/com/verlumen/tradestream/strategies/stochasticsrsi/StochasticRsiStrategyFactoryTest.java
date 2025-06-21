package com.verlumen.tradestream.strategies.stochasticsrsi;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.StochasticRsiParameters;
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
import org.ta4j.core.indicators.RSIIndicator;
import org.ta4j.core.indicators.StochasticOscillatorKIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;

@RunWith(JUnit4.class)
public class StochasticRsiStrategyFactoryTest {
  private static final int RSI_PERIOD = 14;
  private static final int STOCHASTIC_K_PERIOD = 14;
  private static final int STOCHASTIC_D_PERIOD = 3;
  private static final int OVERBOUGHT_THRESHOLD = 80;
  private static final int OVERSOLD_THRESHOLD = 20;

  private StochasticRsiStrategyFactory factory;
  private StochasticRsiParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging RSI and Stochastic calculations
  private RSIIndicator rsiIndicator;
  private StochasticOscillatorKIndicator stochasticK;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new StochasticRsiStrategyFactory();

    // Standard parameters
    params =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create sample price data to generate RSI and Stochastic patterns
    // Start with declining prices to create low RSI values
    double price = 100.0;
    for (int i = 0; i < 15; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price -= 2.0; // Declining prices
    }

    // Strong upward movement to create high RSI values
    for (int i = 15; i < 25; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price += 5.0; // Strong upward movement
    }

    // More data for stability
    for (int i = 25; i < 35; i++) {
      series.addBar(createBar(now.plusMinutes(i), price));
      price += 1.0; // Continued upward movement
    }

    // Indicators
    closePrice = new ClosePriceIndicator(series);
    rsiIndicator = new RSIIndicator(closePrice, RSI_PERIOD);
    stochasticK = new StochasticOscillatorKIndicator(series, STOCHASTIC_K_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsStochasticRsi() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.STOCHASTIC_RSI);
  }

  @Test
  public void entryRule_shouldTrigger_whenStochasticRsiAboveOversold() {
    // Find a bar index where Stochastic K is above oversold threshold
    int entryIndex = -1;
    for (int i = RSI_PERIOD; i < series.getBarCount(); i++) {
      if (stochasticK.getValue(i).doubleValue() > params.getOversoldThreshold()) {
        entryIndex = i;
        break;
      }
    }

    // Log values for debugging
    if (entryIndex > 0) {
      System.out.printf(
          "Entry at Bar %d - Price: %.2f, RSI: %.2f, Stochastic K: %.2f%n",
          entryIndex,
          closePrice.getValue(entryIndex).doubleValue(),
          rsiIndicator.getValue(entryIndex).doubleValue(),
          stochasticK.getValue(entryIndex).doubleValue());
      assertThat(strategy.getEntryRule().isSatisfied(entryIndex)).isTrue();
    } else {
      System.out.println("No entry signal found with current data and parameters.");
    }
  }

  @Test
  public void exitRule_shouldTrigger_whenStochasticRsiBelowOverbought() {
    // Find a bar index where Stochastic K is below overbought threshold
    int exitIndex = -1;
    for (int i = RSI_PERIOD; i < series.getBarCount(); i++) {
      if (stochasticK.getValue(i).doubleValue() < params.getOverboughtThreshold()) {
        exitIndex = i;
        break;
      }
    }

    // Log values for debugging
    if (exitIndex > 0) {
      System.out.printf(
          "Exit at Bar %d - Price: %.2f, RSI: %.2f, Stochastic K: %.2f%n",
          exitIndex,
          closePrice.getValue(exitIndex).doubleValue(),
          rsiIndicator.getValue(exitIndex).doubleValue(),
          stochasticK.getValue(exitIndex).doubleValue());
      assertThat(strategy.getExitRule().isSatisfied(exitIndex)).isTrue();
    } else {
      System.out.println("No exit signal found with current data and parameters.");
    }
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateRsiPeriod() throws InvalidProtocolBufferException {
    params =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(-1)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateStochasticKPeriod() throws InvalidProtocolBufferException {
    params =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setStochasticKPeriod(-1)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateOverboughtThreshold() throws InvalidProtocolBufferException {
    params =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(-1)
            .setOversoldThreshold(OVERSOLD_THRESHOLD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateOversoldThreshold() throws InvalidProtocolBufferException {
    params =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERBOUGHT_THRESHOLD)
            .setOversoldThreshold(-1)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateThresholdOrdering() throws InvalidProtocolBufferException {
    params =
        StochasticRsiParameters.newBuilder()
            .setRsiPeriod(RSI_PERIOD)
            .setStochasticKPeriod(STOCHASTIC_K_PERIOD)
            .setStochasticDPeriod(STOCHASTIC_D_PERIOD)
            .setOverboughtThreshold(OVERSOLD_THRESHOLD)
            .setOversoldThreshold(OVERBOUGHT_THRESHOLD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    StochasticRsiParameters defaultParams = factory.getDefaultParameters();
    
    assertThat(defaultParams.getRsiPeriod()).isEqualTo(14);
    assertThat(defaultParams.getStochasticKPeriod()).isEqualTo(14);
    assertThat(defaultParams.getStochasticDPeriod()).isEqualTo(3);
    assertThat(defaultParams.getOverboughtThreshold()).isEqualTo(80);
    assertThat(defaultParams.getOversoldThreshold()).isEqualTo(20);
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

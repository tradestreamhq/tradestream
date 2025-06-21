package com.verlumen.tradestream.strategies.rvi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RviParameters;
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
import org.ta4j.core.indicators.SMAIndicator;
import org.ta4j.core.indicators.helpers.ClosePriceIndicator;
import org.ta4j.core.indicators.helpers.HighPriceIndicator;
import org.ta4j.core.indicators.helpers.LowPriceIndicator;
import org.ta4j.core.indicators.helpers.OpenPriceIndicator;

@RunWith(JUnit4.class)
public class RviStrategyFactoryTest {
  private static final int RVI_PERIOD = 10;

  private RviStrategyFactory factory;
  private RviParameters params;
  private BaseBarSeries series;
  private Strategy strategy;

  // For debugging RVI calculations
  private RviIndicator rvi;
  private SMAIndicator rviSignal;
  private ClosePriceIndicator closePrice;
  private OpenPriceIndicator openPrice;
  private HighPriceIndicator highPrice;
  private LowPriceIndicator lowPrice;

  @Before
  public void setUp() {
    factory = new RviStrategyFactory();

    // Standard parameters
    params = RviParameters.newBuilder().setPeriod(RVI_PERIOD).build();

    // Initialize series
    series = new BaseBarSeries();
    ZonedDateTime now = ZonedDateTime.now();

    // Create initial stable period with neutral RVI (bars 0-14)
    // Using bars where close ≈ open to create low RVI values
    for (int i = 0; i < 15; i++) {
      double basePrice = 50.0;
      series.addBar(createBar(now.plusMinutes(i), 
          basePrice,      // open
          basePrice + 0.5, // high  
          basePrice - 0.5, // low
          basePrice + 0.1  // close (slightly above open)
      ));
    }

    // Create bullish pattern for entry signal (bars 15-19)
    // RVI should increase when close > open consistently
    for (int i = 15; i < 20; i++) {
      double basePrice = 50.0 + (i - 14) * 2; // Increasing trend
      series.addBar(createBar(now.plusMinutes(i),
          basePrice,      // open
          basePrice + 2.0, // high
          basePrice - 0.5, // low  
          basePrice + 1.5  // close significantly above open
      ));
    }

    // Create bearish pattern for exit signal (bars 20-24)
    // RVI should decrease when close < open consistently  
    for (int i = 20; i < 25; i++) {
      double basePrice = 60.0 - (i - 19) * 2; // Decreasing trend
      series.addBar(createBar(now.plusMinutes(i),
          basePrice,      // open
          basePrice + 0.5, // high
          basePrice - 2.0, // low
          basePrice - 1.5  // close significantly below open
      ));
    }

    // Initialize indicators for debugging
    closePrice = new ClosePriceIndicator(series);
    openPrice = new OpenPriceIndicator(series);
    highPrice = new HighPriceIndicator(series);
    lowPrice = new LowPriceIndicator(series);

    // Use the existing RviIndicator class
    rvi = new RviIndicator(closePrice, openPrice, highPrice, lowPrice, RVI_PERIOD);
    rviSignal = new SMAIndicator(rvi, 4); // 4-period signal line

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void entryRule_shouldTrigger_whenRviCrossesAboveSignalLine() {
    // Log RVI values around the expected crossover
    for (int i = 15; i <= 20; i++) {
      if (i < series.getBarCount()) {
        System.out.printf(
            "Bar %d - Open: %.2f, High: %.2f, Low: %.2f, Close: %.2f, RVI: %.4f, Signal: %.4f%n",
            i,
            openPrice.getValue(i).doubleValue(),
            highPrice.getValue(i).doubleValue(), 
            lowPrice.getValue(i).doubleValue(),
            closePrice.getValue(i).doubleValue(),
            rvi.getValue(i).doubleValue(),
            rviSignal.getValue(i).doubleValue());
      }
    }

    // Find entry signal in the bullish pattern section
    boolean entryFound = false;
    for (int i = 15; i < 20 && i < series.getBarCount(); i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        System.out.println("Entry rule satisfied at bar " + i);
        entryFound = true;
        break;
      }
    }

    assertThat(entryFound).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenRviCrossesBelowSignalLine() {
    // Log RVI values around the expected crossover
    for (int i = 20; i < series.getBarCount(); i++) {
      System.out.printf(
          "Bar %d - Open: %.2f, High: %.2f, Low: %.2f, Close: %.2f, RVI: %.4f, Signal: %.4f%n",
          i,
          openPrice.getValue(i).doubleValue(),
          highPrice.getValue(i).doubleValue(),
          lowPrice.getValue(i).doubleValue(), 
          closePrice.getValue(i).doubleValue(),
          rvi.getValue(i).doubleValue(),
          rviSignal.getValue(i).doubleValue());
    }

    // Find exit signal in the bearish pattern section
    boolean exitFound = false;
    for (int i = 20; i < series.getBarCount(); i++) {
      if (strategy.getExitRule().isSatisfied(i)) {
        System.out.println("Exit rule satisfied at bar " + i);
        exitFound = true;
        break;
      }
    }

    assertThat(exitFound).isTrue();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validatePeriod() {
    params = RviParameters.newBuilder().setPeriod(-1).build();
    factory.createStrategy(series, params);
  }

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    RviParameters defaultParams = factory.getDefaultParameters();
    assertThat(defaultParams.getPeriod()).isEqualTo(10);
    
    // Should be able to create strategy with default parameters
    Strategy defaultStrategy = factory.createStrategy(series, defaultParams);
    assertThat(defaultStrategy).isNotNull();
  }

  /** Helper for creating a Bar with specific OHLC prices. */
  private BaseBar createBar(ZonedDateTime time, double open, double high, double low, double close) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        open,   // open
        high,   // high  
        low,    // low
        close,  // close
        100.0   // volume
    );
  }
}

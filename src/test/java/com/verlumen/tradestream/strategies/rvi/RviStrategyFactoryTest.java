package com.verlumen.tradestream.strategies.rvi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RviParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.indicators.averages.SMAIndicator;
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
    // Phase 1: Create bearish/neutral conditions (bars 0-14)
    // This will create negative or near-zero RVI values
    for (int i = 0; i < 15; i++) {
      double basePrice = 50.0;
      series.addBar(
          createBar(
              now.plusMinutes(i),
              basePrice + 0.2, // open (slightly above base)
              basePrice + 0.5, // high
              basePrice - 0.5, // low
              basePrice - 0.1 // close (below open, bearish)
              ));
    }
    // Phase 2: Transition period to establish RVI below signal line (bars 15-17)
    for (int i = 15; i < 18; i++) {
      double basePrice = 50.0;
      series.addBar(
          createBar(
              now.plusMinutes(i),
              basePrice, // open
              basePrice + 0.3, // high
              basePrice - 0.3, // low
              basePrice // close (neutral, RVI ≈ 0)
              ));
    }
    // Phase 3: Strong bullish pattern for clear entry signal (bars 18-22)
    // This should create a clear cross-up from RVI below signal line to above
    for (int i = 18; i < 23; i++) {
      double basePrice = 50.0 + (i - 17) * 3; // Increasing trend
      series.addBar(
          createBar(
              now.plusMinutes(i),
              basePrice, // open
              basePrice + 3.0, // high
              basePrice - 0.5, // low
              basePrice + 2.5 // close strongly above open (very bullish)
              ));
    }
    // Phase 4: Bearish pattern for exit signal (bars 23-27)
    for (int i = 23; i < 28; i++) {
      double basePrice = 65.0 - (i - 22) * 3; // Decreasing trend
      series.addBar(
          createBar(
              now.plusMinutes(i),
              basePrice, // open
              basePrice + 0.5, // high
              basePrice - 3.0, // low
              basePrice - 2.5 // close strongly below open (very bearish)
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
    System.out.println("=== RVI Entry Test Debug ===");
    for (int i = 15; i <= 22; i++) {
      if (i < series.getBarCount()) {
        double rviValue = rvi.getValue(i).doubleValue();
        double signalValue = rviSignal.getValue(i).doubleValue();
        boolean entryTriggered = strategy.getEntryRule().isSatisfied(i);
        System.out.printf(
            "Bar %d - O:%.2f H:%.2f L:%.2f C:%.2f | RVI:%.4f Signal:%.4f | Entry:%s%n",
            i,
            openPrice.getValue(i).doubleValue(),
            highPrice.getValue(i).doubleValue(),
            lowPrice.getValue(i).doubleValue(),
            closePrice.getValue(i).doubleValue(),
            rviValue,
            signalValue,
            entryTriggered ? "YES" : "no");
      }
    }
    // Find entry signal in the transition and bullish pattern sections
    boolean entryFound = false;
    int entryBar = -1;
    for (int i = 15; i <= 22 && i < series.getBarCount(); i++) {
      if (strategy.getEntryRule().isSatisfied(i)) {
        System.out.println("Entry rule satisfied at bar " + i);
        entryFound = true;
        entryBar = i;
        break;
      }
    }
    // Verify that RVI crossed above signal line at the entry bar
    if (entryFound && entryBar > 0) {
      double rviPrev = rvi.getValue(entryBar - 1).doubleValue();
      double signalPrev = rviSignal.getValue(entryBar - 1).doubleValue();
      double rviCurrent = rvi.getValue(entryBar).doubleValue();
      double signalCurrent = rviSignal.getValue(entryBar).doubleValue();

      System.out.printf(
          "Crossover verification - Prev: RVI=%.4f Signal=%.4f, Current: RVI=%.4f Signal=%.4f%n",
          rviPrev, signalPrev, rviCurrent, signalCurrent);
      // Verify it's actually a cross-up
      assertThat(rviPrev).isAtMost(signalPrev); // RVI was below or equal to signal
      assertThat(rviCurrent).isGreaterThan(signalCurrent); // RVI is now above signal
    }
    assertThat(entryFound).isTrue();
  }

  @Test
  public void exitRule_shouldTrigger_whenRviCrossesBelowSignalLine() {
    // Log RVI values around the expected crossover
    System.out.println("=== RVI Exit Test Debug ===");
    for (int i = 20; i < series.getBarCount(); i++) {
      double rviValue = rvi.getValue(i).doubleValue();
      double signalValue = rviSignal.getValue(i).doubleValue();
      boolean exitTriggered = strategy.getExitRule().isSatisfied(i);
      System.out.printf(
          "Bar %d - O:%.2f H:%.2f L:%.2f C:%.2f | RVI:%.4f Signal:%.4f | Exit:%s%n",
          i,
          openPrice.getValue(i).doubleValue(),
          highPrice.getValue(i).doubleValue(),
          lowPrice.getValue(i).doubleValue(),
          closePrice.getValue(i).doubleValue(),
          rviValue,
          signalValue,
          exitTriggered ? "YES" : "no");
    }
    // Find exit signal in the bearish pattern section (bars 23+)
    boolean exitFound = false;
    int exitBar = -1;
    for (int i = 23; i < series.getBarCount(); i++) {
      if (strategy.getExitRule().isSatisfied(i)) {
        System.out.println("Exit rule satisfied at bar " + i);
        exitFound = true;
        exitBar = i;
        break;
      }
    }
    // Verify that RVI crossed below signal line at the exit bar
    if (exitFound && exitBar > 0) {
      double rviPrev = rvi.getValue(exitBar - 1).doubleValue();
      double signalPrev = rviSignal.getValue(exitBar - 1).doubleValue();
      double rviCurrent = rvi.getValue(exitBar).doubleValue();
      double signalCurrent = rviSignal.getValue(exitBar).doubleValue();

      System.out.printf(
          "Exit crossover verification - Prev: RVI=%.4f Signal=%.4f, Current: RVI=%.4f"
              + " Signal=%.4f%n",
          rviPrev, signalPrev, rviCurrent, signalCurrent);
      // Verify it's actually a cross-down
      assertThat(rviPrev).isGreaterThan(signalPrev); // RVI was above signal
      assertThat(rviCurrent).isLessThan(signalCurrent); // RVI is now below signal
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
  private BaseBar createBar(
      ZonedDateTime time, double open, double high, double low, double close) {
    return new BaseBar(
        Duration.ofMinutes(1),
        time,
        open, // open
        high, // high
        low, // low
        close, // close
        100.0 // volume
        );
  }
}

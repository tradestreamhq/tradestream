package com.verlumen.tradestream.strategies.aroonmfi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.AroonMfiParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public class AroonMfiStrategyFactoryTest {
  private AroonMfiStrategyFactory factory;
  private BarSeries series;

  @Before
  public void setUp() {
    factory = new AroonMfiStrategyFactory();
    series = new BaseBarSeries();
    
    // Create more realistic test data with varying prices and volumes
    ZonedDateTime startTime = ZonedDateTime.now();
    for (int i = 0; i < 50; i++) {
      double price = 100 + i + (Math.sin(i * 0.1) * 5); // Varying price pattern
      long volume = 1000 + (i * 10); // Increasing volume
      series.addBar(
          new BaseBar(
              Duration.ofDays(1), 
              startTime.plusDays(i), 
              price, 
              price + 2, 
              price - 1, 
              price + 1, 
              volume));
    }
  }

  @Test
  public void testCreateStrategy() {
    AroonMfiParameters params =
        AroonMfiParameters.newBuilder()
            .setAroonPeriod(25)
            .setMfiPeriod(14)
            .setOverboughtThreshold(80)
            .setOversoldThreshold(20)
            .build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getName()).contains("AROON_MFI");
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativeAroonPeriod() {
    AroonMfiParameters params =
        AroonMfiParameters.newBuilder()
            .setAroonPeriod(-1)
            .setMfiPeriod(14)
            .setOverboughtThreshold(80)
            .setOversoldThreshold(20)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_negativeMfiPeriod() {
    AroonMfiParameters params =
        AroonMfiParameters.newBuilder()
            .setAroonPeriod(25)
            .setMfiPeriod(-1)
            .setOverboughtThreshold(80)
            .setOversoldThreshold(20)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_invalidThresholds() {
    AroonMfiParameters params =
        AroonMfiParameters.newBuilder()
            .setAroonPeriod(25)
            .setMfiPeriod(14)
            .setOverboughtThreshold(20)  // Lower than oversold
            .setOversoldThreshold(80)
            .build();
    factory.createStrategy(series, params);
  }

  @Test
  public void testGetDefaultParameters() {
    AroonMfiParameters defaultParams = factory.getDefaultParameters();
    assertThat(defaultParams.getAroonPeriod()).isEqualTo(25);
    assertThat(defaultParams.getMfiPeriod()).isEqualTo(14);
    assertThat(defaultParams.getOverboughtThreshold()).isEqualTo(80);
    assertThat(defaultParams.getOversoldThreshold()).isEqualTo(20);
  }

  @Test
  public void testStrategyExecutesWithoutErrors() {
    AroonMfiParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    
    // Test that the strategy can evaluate at different indices without throwing exceptions
    // Start from a higher index to ensure we have enough data for all indicators
    for (int i = Math.max(25, strategy.getUnstableBars()); i < series.getBarCount(); i++) {
      boolean shouldEnter = strategy.shouldEnter(i);
      boolean shouldExit = strategy.shouldExit(i);
      // Both can be false, but shouldn't throw exceptions
      assertThat(shouldEnter || !shouldEnter).isTrue(); // Always true, just checking no exception
      assertThat(shouldExit || !shouldExit).isTrue();   // Always true, just checking no exception
    }
  }
}

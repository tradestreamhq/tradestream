package com.verlumen.tradestream.strategies.movingaverages;

import static com.google.common.truth.Truth.assertThat;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.MomentumSmaCrossoverParameters;
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

@RunWith(JUnit4.class)
public class MomentumSmaCrossoverStrategyFactoryTest {
  private static final int MOMENTUM_PERIOD = 10;
  private static final int SMA_PERIOD = 20;

  private MomentumSmaCrossoverStrategyFactory factory;
  private MomentumSmaCrossoverParameters params;
  private BaseBarSeries series;
  private Strategy strategy;
  private ZonedDateTime startTime;

  // For debugging calculations
  private MomentumIndicator momentumIndicator;
  private SMAIndicator smaIndicator;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = MomentumSmaCrossoverStrategyFactory.create();
    params =
        MomentumSmaCrossoverParameters.newBuilder()
            .setMomentumPeriod(MOMENTUM_PERIOD)
            .setSmaPeriod(SMA_PERIOD)
            .build();

    series = new BaseBarSeries();
    startTime = ZonedDateTime.now();

    // Create initial stable period (bars 0-19)
    for (int i = 0; i < 20; i++) {
      series.addBar(createBar(startTime.plusMinutes(i), 50.0));
    }

    // Create momentum period for entry setup (bars 20-29)
    // Start a gradual uptrend to generate positive momentum
    for (int i = 20; i < 30; i++) {
      double price = 50.0 + (i - 19) * 2; // Increasing by 2 each bar
      series.addBar(createBar(startTime.plusMinutes(i), price));
    }

    // Accelerate uptrend to force momentum above SMA (bars 30-34)
    for (int i = 30; i < 35; i++) {
      double price = 70.0 + (i - 29) * 4; // Increasing by 4 each bar
      series.addBar(createBar(startTime.plusMinutes(i), price));
    }

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);
  }

  @Test
  public void getStrategyType_returnsMomentumSmaCrossover() {
    assertThat(factory.getStrategyType()).isEqualTo(StrategyType.MOMENTUM_SMA_CROSSOVER);
  }

  @Test
  public void entryRule_shouldTrigger_whenMomentumCrossesAboveSma()
      throws InvalidProtocolBufferException {
    series = new BaseBarSeries();

    // Initial period with stable prices (15 bars)
    for (int i = 0; i < 15; i++) {
      series.addBar(createBar(startTime.plusMinutes(i), 100.0));
    }

    // Create decline then rise for crossover (5 bars)
    series.addBar(createBar(startTime.plusMinutes(15), 98.0));
    series.addBar(createBar(startTime.plusMinutes(16), 98.0));
    series.addBar(createBar(startTime.plusMinutes(17), 99.0)); // Bar i-2
    series.addBar(createBar(startTime.plusMinutes(18), 102.0)); // Bar i-1 - Crossover
    series.addBar(createBar(startTime.plusMinutes(19), 103.0)); // Bar i

    // Reinitialize
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);
    strategy = factory.createStrategy(series, params);

    int lastIndex = series.getBarCount() - 1;

    // Log debug info
    System.out.println("Series size: " + series.getBarCount());
    System.out.println(
        "Testing bars: " + (lastIndex - 2) + ", " + (lastIndex - 1) + ", " + lastIndex);

    // Test with actual indices
    assertThat(strategy.getEntryRule().isSatisfied(lastIndex - 2)).isFalse();
    assertThat(strategy.getEntryRule().isSatisfied(lastIndex - 1)).isTrue();
    assertThat(strategy.getEntryRule().isSatisfied(lastIndex)).isFalse();
  }

  @Test
  public void exitRule_shouldTrigger_whenMomentumCrossesBelowSma()
      throws InvalidProtocolBufferException {
    series = new BaseBarSeries();

    // Initial period with stable prices (15 bars)
    for (int i = 0; i < 15; i++) {
      series.addBar(createBar(startTime.plusMinutes(i), 100.0));
    }

    // Create rise then sharp decline for crossover (5 bars)
    series.addBar(createBar(startTime.plusMinutes(15), 110.0));
    series.addBar(createBar(startTime.plusMinutes(16), 110.0));
    series.addBar(createBar(startTime.plusMinutes(17), 105.0)); // Bar i-2
    series.addBar(createBar(startTime.plusMinutes(18), 95.0)); // Bar i-1 - Crossover
    series.addBar(createBar(startTime.plusMinutes(19), 92.0)); // Bar i

    // Reinitialize
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);
    strategy = factory.createStrategy(series, params);

    int lastIndex = series.getBarCount() - 1;

    // Log debug info
    System.out.println("Series size: " + series.getBarCount());
    System.out.println(
        "Testing bars: " + (lastIndex - 2) + ", " + (lastIndex - 1) + ", " + lastIndex);

    // Test with actual indices
    assertThat(strategy.getExitRule().isSatisfied(lastIndex - 2)).isFalse();
    assertThat(strategy.getExitRule().isSatisfied(lastIndex - 1)).isTrue();
    assertThat(strategy.getExitRule().isSatisfied(lastIndex)).isFalse();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateMomentumPeriod() throws InvalidProtocolBufferException {
    params =
        MomentumSmaCrossoverParameters.newBuilder()
            .setMomentumPeriod(-1)
            .setSmaPeriod(SMA_PERIOD)
            .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateSmaPeriod() throws InvalidProtocolBufferException {
    params =
        MomentumSmaCrossoverParameters.newBuilder()
            .setMomentumPeriod(MOMENTUM_PERIOD)
            .setSmaPeriod(-1)
            .build();
    factory.createStrategy(series, params);
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

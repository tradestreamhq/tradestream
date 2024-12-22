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
    factory = new MomentumSmaCrossoverStrategyFactory();
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
  public void entryRule_shouldTrigger_whenMomentumCrossesAboveSma() throws InvalidProtocolBufferException {
    // Reset series with data that will create a proper crossover
    series = new BaseBarSeries();
    
    // Create initial period with flat prices to establish baseline
    for (int i = 0; i < 25; i++) {
        series.addBar(createBar(startTime.plusMinutes(i), 50.0));
    }
    
    // Create gradual momentum buildup
    for (int i = 25; i < 30; i++) {
        double price = 50.0 + (i - 24); // Increase by 1 each bar
        series.addBar(createBar(startTime.plusMinutes(i), price));
    }
    
    // Create crossover point
    series.addBar(createBar(startTime.plusMinutes(30), 56.0));
    series.addBar(createBar(startTime.plusMinutes(31), 58.0)); // Bar where crossover happens
    series.addBar(createBar(startTime.plusMinutes(32), 59.0));
    
    // Reinitialize indicators with new data
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);
    strategy = factory.createStrategy(series, params);
    
    // Print values around crossover point
    for (int i = 30; i < 33; i++) {
        System.out.printf(
            "Bar %d - Price: %.2f, Momentum: %.2f, SMA: %.2f%n",
            i,
            closePrice.getValue(i).doubleValue(),
            momentumIndicator.getValue(i).doubleValue(),
            smaIndicator.getValue(i).doubleValue());
    }
    
    assertThat(strategy.getEntryRule().isSatisfied(30)).isFalse();
    assertThat(strategy.getEntryRule().isSatisfied(31)).isTrue();
    assertThat(strategy.getEntryRule().isSatisfied(32)).isFalse();
  }

  @Test
  public void exitRule_shouldTrigger_whenMomentumCrossesBelowSma() throws InvalidProtocolBufferException {
    // First set up entry conditions
    series = new BaseBarSeries();
    
    // Initial period
    for (int i = 0; i < 25; i++) {
        series.addBar(createBar(startTime.plusMinutes(i), 50.0));
    }
    
    // Create uptrend to establish positive momentum
    for (int i = 25; i < 35; i++) {
        double price = 50.0 + ((i - 24) * 2); 
        series.addBar(createBar(startTime.plusMinutes(i), price));
    }
    
    // Create downtrend to force momentum down
    for (int i = 35; i < 40; i++) {
        double price = 70.0 - ((i - 34) * 3);
        series.addBar(createBar(startTime.plusMinutes(i), price));
    }
    
    // Create crossover point
    series.addBar(createBar(startTime.plusMinutes(40), 55.0));
    series.addBar(createBar(startTime.plusMinutes(41), 52.0)); // Bar where crossover happens
    series.addBar(createBar(startTime.plusMinutes(42), 50.0));
    
    // Reinitialize indicators with new data
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);
    strategy = factory.createStrategy(series, params);
    
    // Print values around crossover point
    for (int i = 40; i < 43; i++) {
        System.out.printf(
            "Bar %d - Price: %.2f, Momentum: %.2f, SMA: %.2f%n",
            i,
            closePrice.getValue(i).doubleValue(),
            momentumIndicator.getValue(i).doubleValue(),
            smaIndicator.getValue(i).doubleValue());
    }
    
    assertThat(strategy.getExitRule().isSatisfied(40)).isFalse();
    assertThat(strategy.getExitRule().isSatisfied(41)).isTrue();
    assertThat(strategy.getExitRule().isSatisfied(42)).isFalse();
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

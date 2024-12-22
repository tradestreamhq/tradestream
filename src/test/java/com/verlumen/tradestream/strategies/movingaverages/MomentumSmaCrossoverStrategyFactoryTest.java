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
  private ZonedDateTime now;

  // For debugging calculations
  private MomentumIndicator momentumIndicator;
  private SMAIndicator smaIndicator;
  private ClosePriceIndicator closePrice;

  @Before
  public void setUp() throws InvalidProtocolBufferException {
    factory = new MomentumSmaCrossoverStrategyFactory();
    params = MomentumSmaCrossoverParameters.newBuilder()
        .setMomentumPeriod(MOMENTUM_PERIOD)
        .setSmaPeriod(SMA_PERIOD)
        .build();

    series = new BaseBarSeries();
    now = ZonedDateTime.now();

    // 1) Baseline: bars 0..4
    double price = 50.0;
    for (int i = 0; i < 5; i++) {
        series.addBar(createBar(now.plusMinutes(i), price));
        price -= 1.0; // 50, 49, 48, 47, 46
    }

    // 2) Downward movement: bar5 = 45.0 → momentum=-5
    series.addBar(createBar(now.plusMinutes(5), 45.0));

    // 3) Slight downward movement: bar6 = 44.0 → momentum=-5
    series.addBar(createBar(now.plusMinutes(6), 44.0));

    // 4) Upward movement: bars7..9
    series.addBar(createBar(now.plusMinutes(7), 60.0)); // momentum=60-49=11
    series.addBar(createBar(now.plusMinutes(8), 70.0)); // momentum=70-48=22
    series.addBar(createBar(now.plusMinutes(9), 40.0)); // momentum=40-47=-7

    // 5) Upward jump: bar10=90.0 → momentum=90-46=44
    series.addBar(createBar(now.plusMinutes(10), 90.0));

    // 6) Downward movement: bars11..12
    series.addBar(createBar(now.plusMinutes(11), 40.0)); // momentum=40-60=-20
    series.addBar(createBar(now.plusMinutes(12), 30.0)); // momentum=30-70=-40

    // Initialize indicators
    closePrice = new ClosePriceIndicator(series);
    momentumIndicator = new MomentumIndicator(closePrice, MOMENTUM_PERIOD);
    smaIndicator = new SMAIndicator(momentumIndicator, SMA_PERIOD);

    // Create strategy
    strategy = factory.createStrategy(series, params);

    // Generate more bars for stable indicator values
    for (int i = 13; i < MOMENTUM_PERIOD + SMA_PERIOD + 5; i++) {
        series.addBar(createBar(now.plusMinutes(i), 50.0 + i));
    }
  }

  @Test
  public void getStrategyType_returnsMomentumSmaCrossover() {
      assertThat(factory.getStrategyType()).isEqualTo(StrategyType.MOMENTUM_SMA_CROSSOVER);
  }

  @Test
  public void entryRule_shouldTrigger_whenMomentumCrossesAboveSma() {
    int crossoverIndex = MOMENTUM_PERIOD + SMA_PERIOD - 1;

    // Log indicator values around expected crossover point
    for (int i = crossoverIndex - 1; i <= crossoverIndex + 1; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, Momentum: %.2f, SMA: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          momentumIndicator.getValue(i).doubleValue(),
          smaIndicator.getValue(i).doubleValue());
    }

    assertThat(strategy.getEntryRule().isSatisfied(crossoverIndex - 1)).isFalse();
    assertThat(strategy.getEntryRule().isSatisfied(crossoverIndex)).isTrue();
    assertThat(strategy.getEntryRule().isSatisfied(crossoverIndex + 1)).isFalse();
  }

  @Test
  public void exitRule_shouldTrigger_whenMomentumCrossesBelowSma() {
    int crossoverIndex = MOMENTUM_PERIOD + SMA_PERIOD + 1;
    series.addBar(createBar(now.plusMinutes(crossoverIndex + 1), 10.0)); // Force downward crossover

    // Log indicator values around expected crossover point
    for (int i = crossoverIndex - 1; i <= crossoverIndex + 1; i++) {
      System.out.printf(
          "Bar %d - Price: %.2f, Momentum: %.2f, SMA: %.2f%n",
          i,
          closePrice.getValue(i).doubleValue(),
          momentumIndicator.getValue(i).doubleValue(),
          smaIndicator.getValue(i).doubleValue());
    }

    assertThat(strategy.getExitRule().isSatisfied(crossoverIndex)).isFalse();
    assertThat(strategy.getExitRule().isSatisfied(crossoverIndex + 1)).isTrue();
    assertThat(strategy.getExitRule().isSatisfied(crossoverIndex + 2)).isFalse();
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateMomentumPeriod() throws InvalidProtocolBufferException {
    params = MomentumSmaCrossoverParameters.newBuilder()
      .setMomentumPeriod(-1)
      .setSmaPeriod(SMA_PERIOD)
      .build();
    factory.createStrategy(series, params);
  }

  @Test(expected = IllegalArgumentException.class)
  public void validateSmaPeriod() throws InvalidProtocolBufferException {
    params = MomentumSmaCrossoverParameters.newBuilder()
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
      100.0  // volume
    );
  }
}

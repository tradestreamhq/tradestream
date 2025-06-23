package com.verlumen.tradestream.strategies.renkochart;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RenkoChartParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;
import org.ta4j.core.TradingRecord;

public final class RenkoChartStrategyFactoryTest {
  private final RenkoChartStrategyFactory factory = new RenkoChartStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    RenkoChartParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.hasBrickSize()).isTrue();
  }

  @Test
  public void testCreateStrategy_returnsNonNull() {
    BarSeries series = new BaseBarSeries();
    RenkoChartParameters params = factory.getDefaultParameters();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }

  @Test
  public void testEntryAndExitRules() {
    // Create a synthetic series with price jumps
    BarSeries series = new BaseBarSeries();
    double[] prices = {100, 100.5, 101, 102, 101.5, 100.5, 99.5, 98.5};
    for (double price : prices) {
      series.addBar(
          new BaseBar(Duration.ofMinutes(1), ZonedDateTime.now(), price, price, price, price, 100));
    }
    RenkoChartParameters params = RenkoChartParameters.newBuilder().setBrickSize(1.0).build();
    Strategy strategy = factory.createStrategy(series, params);
    TradingRecord record = new org.ta4j.core.BaseTradingRecord();
    // Entry should trigger at index 3 (price 102)
    boolean entry = strategy.getEntryRule().isSatisfied(3, record);
    assertThat(entry).isTrue();
    // Exit should trigger at index 6 (price 99.5)
    boolean exit = strategy.getExitRule().isSatisfied(6, record);
    assertThat(exit).isTrue();
  }
}

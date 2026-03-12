package com.verlumen.tradestream.strategies.regressionchannel;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RegressionChannelParameters;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.ta4j.core.num.DecimalNum;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

public final class RegressionChannelStrategyFactoryTest {
  private final RegressionChannelStrategyFactory factory = new RegressionChannelStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    RegressionChannelParameters params = factory.getDefaultParameters();
    assertThat(params).isNotNull();
    assertThat(params.getPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateStrategy() {
    BarSeries series = new BaseBarSeriesBuilder().build();
    // Add some bars
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 30; i++) {
      Duration duration = Duration.ofMinutes(1);
      Instant endTime = now.plusMinutes(i).toInstant();
      Instant beginTime = endTime.minus(duration);
      series.addBar(
          new BaseBar(
              duration,
              beginTime,
              endTime,
              DecimalNum.valueOf(100 + i),
              DecimalNum.valueOf(101 + i),
              DecimalNum.valueOf(99 + i),
              DecimalNum.valueOf(100 + i),
              DecimalNum.valueOf(1000),
              DecimalNum.valueOf(0),
              0));
    }
    RegressionChannelParameters params =
        RegressionChannelParameters.newBuilder().setPeriod(20).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}

package com.verlumen.tradestream.strategies.heikenashi;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.HeikenAshiParameters;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.ta4j.core.num.DecimalNum;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

@RunWith(JUnit4.class)
public class HeikenAshiStrategyFactoryTest {
  private HeikenAshiStrategyFactory factory;
  private HeikenAshiParameters params;
  private BaseBarSeries series;

  @Before
  public void setUp() {
    factory = new HeikenAshiStrategyFactory();
    params = HeikenAshiParameters.newBuilder().setPeriod(14).build();
    series = new BaseBarSeriesBuilder().build();
    // Add some bars
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 20; i++) {
      Duration duration = Duration.ofMinutes(1);
      Instant endTime = now.plusMinutes(i).toInstant();
      Instant beginTime = endTime.minus(duration);
      series.addBar(
          new BaseBar(
              duration, beginTime, endTime,
              DecimalNum.valueOf(1), DecimalNum.valueOf(2),
              DecimalNum.valueOf(0.5), DecimalNum.valueOf(1.5),
              DecimalNum.valueOf(100), DecimalNum.valueOf(0), 0));
    }
  }

  @Test
  public void testCreateStrategy_returnsNonNull() {
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
  }

  @Test(expected = IllegalArgumentException.class)
  public void testCreateStrategy_invalidParams_throws() {
    HeikenAshiParameters badParams = HeikenAshiParameters.newBuilder().setPeriod(0).build();
    factory.createStrategy(series, badParams);
  }
}

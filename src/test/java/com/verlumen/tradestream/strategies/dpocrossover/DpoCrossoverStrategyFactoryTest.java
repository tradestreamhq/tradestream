package com.verlumen.tradestream.strategies.dpocrossover;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.DpoCrossoverParameters;
import java.time.Duration;
import java.time.Instant;
import java.time.ZonedDateTime;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.junit.runners.JUnit4;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

@RunWith(JUnit4.class)
public final class DpoCrossoverStrategyFactoryTest {
  private DpoCrossoverStrategyFactory factory;

  @Before
  public void setUp() {
    factory = new DpoCrossoverStrategyFactory();
  }

  @Test
  public void getDefaultParameters_returnsValid() {
    DpoCrossoverParameters params = factory.getDefaultParameters();
    assertThat(params.getDpoPeriod()).isGreaterThan(0);
    assertThat(params.getMaPeriod()).isGreaterThan(0);
  }

  @Test
  public void createStrategy_returnsNonNull() throws Exception {
    BarSeries series = new BaseBarSeriesBuilder().build();
    ZonedDateTime now = ZonedDateTime.now();
    for (int i = 0; i < 50; i++) {
      Duration duration = Duration.ofMinutes(1);
      Instant endTime = now.plusMinutes(i).toInstant();
      Instant beginTime = endTime.minus(duration);
      series.addBar(
          new BaseBar(
              duration,
              beginTime,
              endTime,
              DecimalNum.valueOf(1 + i),
              DecimalNum.valueOf(2 + i),
              DecimalNum.valueOf(0.5 + i),
              DecimalNum.valueOf(1.5 + i),
              DecimalNum.valueOf(100 + i),
              DecimalNum.valueOf(0),
              0));
    }
    DpoCrossoverParameters params =
        DpoCrossoverParameters.newBuilder().setDpoPeriod(20).setMaPeriod(10).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}

package com.verlumen.tradestream.strategies.elderrayma;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.ElderRayMAParameters;
import java.time.Duration;
import java.time.ZonedDateTime;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBar;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;
import org.ta4j.core.num.DecimalNum;

public final class ElderRayMAStrategyFactoryTest {
  private final ElderRayMAStrategyFactory factory = new ElderRayMAStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    ElderRayMAParameters params = factory.getDefaultParameters();
    assertThat(params.getEmaPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateStrategy() {
    BarSeries series = new BaseBarSeriesBuilder().withName("test").build();
    ZonedDateTime now = ZonedDateTime.now();
    // Add some bars to the series for indicator calculation
    for (int i = 1; i <= 30; i++) {
      series.addBar(
          new BaseBar(
              Duration.ofMinutes(1),
              now.plusMinutes(i - 1).toInstant(),
              now.plusMinutes(i).toInstant(),
              DecimalNum.valueOf(100 + i),
              DecimalNum.valueOf(105 + i),
              DecimalNum.valueOf(95 + i),
              DecimalNum.valueOf(100 + i),
              DecimalNum.valueOf(1000),
              DecimalNum.valueOf(0),
              0));
    }
    ElderRayMAParameters params = ElderRayMAParameters.newBuilder().setEmaPeriod(10).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}

package com.verlumen.tradestream.strategies.elderrayma;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.ElderRayMAParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

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
    // Add some bars to the series for indicator calculation
    for (int i = 0; i < 30; i++) {
      series.addBar(
          org.ta4j.core.BaseBar.builder()
              .timePeriod(java.time.Duration.ofMinutes(1))
              .endTime(java.time.ZonedDateTime.now().plusMinutes(i + 1))
              .openPrice(org.ta4j.core.num.DecimalNum.valueOf(100 + i))
              .highPrice(org.ta4j.core.num.DecimalNum.valueOf(105 + i))
              .lowPrice(org.ta4j.core.num.DecimalNum.valueOf(95 + i))
              .closePrice(org.ta4j.core.num.DecimalNum.valueOf(100 + i))
              .volume(org.ta4j.core.num.DecimalNum.valueOf(1000))
              .build());
    }
    ElderRayMAParameters params = ElderRayMAParameters.newBuilder().setEmaPeriod(10).build();
    Strategy strategy = factory.createStrategy(series, params);
    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}

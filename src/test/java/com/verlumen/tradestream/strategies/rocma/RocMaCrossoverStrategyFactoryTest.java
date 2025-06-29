package com.verlumen.tradestream.strategies.rocma;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.RocMaCrossoverParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeriesBuilder;
import org.ta4j.core.Strategy;

public final class RocMaCrossoverStrategyFactoryTest {
  private final RocMaCrossoverStrategyFactory factory = new RocMaCrossoverStrategyFactory();

  @Test
  public void testGetDefaultParameters() {
    RocMaCrossoverParameters params = factory.getDefaultParameters();
    assertThat(params.getRocPeriod()).isEqualTo(10);
    assertThat(params.getMaPeriod()).isEqualTo(20);
  }

  @Test
  public void testCreateStrategy() {
    BarSeries series = new BaseBarSeriesBuilder().withName("test").build();
    RocMaCrossoverParameters params =
        RocMaCrossoverParameters.newBuilder().setRocPeriod(5).setMaPeriod(10).build();

    Strategy strategy = factory.createStrategy(series, params);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
    assertThat(strategy.getName()).isEqualTo("ROC_MA_CROSSOVER");
  }
}

package com.verlumen.tradestream.strategies.volumeprofile;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.VolumeProfileParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class VolumeProfileStrategyFactoryTest {

  private final VolumeProfileStrategyFactory factory = new VolumeProfileStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    VolumeProfileParameters parameters = factory.getDefaultParameters();

    assertThat(parameters).isNotNull();
    assertThat(parameters.getPeriod()).isEqualTo(20);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    BarSeries series = new BaseBarSeries();
    VolumeProfileParameters parameters = VolumeProfileParameters.newBuilder().setPeriod(30).build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
}

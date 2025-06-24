package com.verlumen.tradestream.strategies.volumeprofiledeviations;

import static com.google.common.truth.Truth.assertThat;

import com.verlumen.tradestream.strategies.VolumeProfileDeviationsParameters;
import org.junit.Test;
import org.ta4j.core.BarSeries;
import org.ta4j.core.BaseBarSeries;
import org.ta4j.core.Strategy;

public final class VolumeProfileDeviationsStrategyFactoryTest {

  private final VolumeProfileDeviationsStrategyFactory factory = new VolumeProfileDeviationsStrategyFactory();

  @Test
  public void getDefaultParameters_returnsValidParameters() {
    VolumeProfileDeviationsParameters parameters = factory.getDefaultParameters();

    assertThat(parameters).isNotNull();
    assertThat(parameters.getPeriod()).isEqualTo(20);
  }

  @Test
  public void createStrategy_returnsValidStrategy() {
    BarSeries series = new BaseBarSeries();
    VolumeProfileDeviationsParameters parameters = VolumeProfileDeviationsParameters.newBuilder()
        .setPeriod(30)
        .build();

    Strategy strategy = factory.createStrategy(series, parameters);

    assertThat(strategy).isNotNull();
    assertThat(strategy.getEntryRule()).isNotNull();
    assertThat(strategy.getExitRule()).isNotNull();
  }
} 
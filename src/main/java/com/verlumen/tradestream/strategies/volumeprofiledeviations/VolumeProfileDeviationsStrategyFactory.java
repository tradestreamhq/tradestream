package com.verlumen.tradestream.strategies.volumeprofiledeviations;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VolumeProfileDeviationsParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

public final class VolumeProfileDeviationsStrategyFactory
    implements StrategyFactory<VolumeProfileDeviationsParameters> {

  @Override
  public VolumeProfileDeviationsParameters getDefaultParameters() {
    return VolumeProfileDeviationsParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VolumeProfileDeviationsParameters parameters) {
    AlwaysTrueRule alwaysTrueRule = new AlwaysTrueRule();
    return new org.ta4j.core.BaseStrategy(alwaysTrueRule, alwaysTrueRule, parameters.getPeriod());
  }
}

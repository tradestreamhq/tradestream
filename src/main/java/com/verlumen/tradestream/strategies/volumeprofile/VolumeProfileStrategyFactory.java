package com.verlumen.tradestream.strategies.volumeprofile;

import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.VolumeProfileParameters;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

public final class VolumeProfileStrategyFactory
    implements StrategyFactory<VolumeProfileParameters> {

  @Override
  public VolumeProfileParameters getDefaultParameters() {
    return VolumeProfileParameters.newBuilder().setPeriod(20).build();
  }

  @Override
  public Strategy createStrategy(BarSeries series, VolumeProfileParameters parameters) {
    AlwaysTrueRule alwaysTrueRule = new AlwaysTrueRule();
    return new org.ta4j.core.BaseStrategy(alwaysTrueRule, alwaysTrueRule, parameters.getPeriod());
  }
}

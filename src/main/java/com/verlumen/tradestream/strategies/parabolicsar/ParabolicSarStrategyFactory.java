package com.verlumen.tradestream.strategies.parabolicsar;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.ParabolicSarParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

public class ParabolicSarStrategyFactory implements StrategyFactory<ParabolicSarParameters> {

  @Override
  public Strategy createStrategy(BarSeries series, ParabolicSarParameters parameters)
      throws InvalidProtocolBufferException {
    // Placeholder: Actual logic to be implemented later.
    throw new UnsupportedOperationException("ParabolicSar strategy logic not yet implemented.");
  }

  @Override
  public ParabolicSarParameters getDefaultParameters() {
    // Delegate to the ParamConfig for default parameters
    return new ParabolicSarParamConfig().getDefaultParameters();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.PARABOLIC_SAR;
  }
}

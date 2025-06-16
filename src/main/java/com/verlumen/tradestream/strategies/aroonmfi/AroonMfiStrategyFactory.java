package com.verlumen.tradestream.strategies.aroonmfi;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.AroonMfiParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;

public class AroonMfiStrategyFactory implements StrategyFactory<AroonMfiParameters> {

  @Override
  public Strategy createStrategy(BarSeries series, AroonMfiParameters parameters)
      throws InvalidProtocolBufferException {
    // Placeholder: Actual logic to be implemented later.
    throw new UnsupportedOperationException("AroonMFI strategy logic not yet implemented.");
  }

  @Override
  public AroonMfiParameters getDefaultParameters() {
    // Delegate to the ParamConfig for default parameters
    return new AroonMfiParamConfig().getDefaultParameters();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.AROON_MFI;
  }
}

package com.verlumen.tradestream.strategies.ichimokucloud;

import com.google.protobuf.InvalidProtocolBufferException;
import com.verlumen.tradestream.strategies.IchimokuCloudParameters;
import com.verlumen.tradestream.strategies.StrategyFactory;
import com.verlumen.tradestream.strategies.StrategyType;
import org.ta4j.core.BarSeries;
import org.ta4j.core.Strategy;
// No BaseStrategy needed if createStrategy throws.

public class IchimokuCloudStrategyFactory implements StrategyFactory<IchimokuCloudParameters> {

  @Override
  public Strategy createStrategy(BarSeries series, IchimokuCloudParameters parameters)
      throws InvalidProtocolBufferException {
    // Placeholder: Actual logic to be implemented later.
    throw new UnsupportedOperationException("IchimokuCloud strategy logic not yet implemented.");
  }

  @Override
  public IchimokuCloudParameters getDefaultParameters() {
    // Delegate to the ParamConfig for default parameters
    return new IchimokuCloudParamConfig().getDefaultParameters();
  }

  @Override
  public StrategyType getStrategyType() {
    return StrategyType.ICHIMOKU_CLOUD;
  }
}
